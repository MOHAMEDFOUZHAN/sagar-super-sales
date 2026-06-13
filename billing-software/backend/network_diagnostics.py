import os
import json
import time
import socket
import ctypes
import subprocess
import re
import psutil
from concurrent.futures import ThreadPoolExecutor, as_completed

CONFIG_DIR = "Configuration"
DEVICE_LABELS_FILE = os.path.join(CONFIG_DIR, "device_labels.json")
ALERTS_LOG_FILE = os.path.join(CONFIG_DIR, "alerts_log.json")

# In-memory store for tracking live traffic calculations
LAST_IO_STATS = {}  # {interface_name: (bytes_sent, bytes_recv, timestamp)}
LAST_SCAN_RESULTS = []

# Common MAC vendor prefixes for offline prefix-matching lookup
MAC_VENDORS = {
    "00:00:5E": "IANA",
    "00:1A:11": "Cisco",
    "00:0C:29": "VMware",
    "00:15:5D": "Microsoft",
    "3C:5A:37": "Intel",
    "70:5A:0F": "Realtek",
    "74:E1:B6": "TP-Link",
    "A4:77:33": "Apple",
    "FC:EC:DA": "Ubiquiti",
    "00:11:32": "Synology",
    "BC:54:51": "Samsung",
    "00:26:08": "Intel",
    "2C:30:11": "D-Link",
    "30:FD:38": "Huawei"
}

def ensure_config_dir():
    if not os.path.exists(CONFIG_DIR):
        os.makedirs(CONFIG_DIR)

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except:
        return False

# --- FEATURE 1: Network Interface Monitor ---
def get_network_interfaces():
    ensure_config_dir()
    global LAST_IO_STATS
    
    stats = psutil.net_if_stats()
    addrs = psutil.net_if_addrs()
    io_counters = psutil.net_io_counters(pernic=True)
    current_time = time.time()
    
    interfaces = []
    
    for name, info in stats.items():
        if name not in addrs:
            continue
            
        # Extract IP and MAC address
        ip_addr = "N/A"
        mac_addr = "N/A"
        for addr in addrs[name]:
            if addr.family == socket.AF_INET:
                ip_addr = addr.address
            elif addr.family == psutil.AF_LINK:
                mac_addr = addr.address
                
        # Connection status & negotiated speed
        is_up = info.isup
        speed = info.speed  # speed in Mbps
        
        # Classify interface type based on name keywords
        lower_name = name.lower()
        is_wireless = "wi-fi" in lower_name or "wlan" in lower_name or "wireless" in lower_name
        is_loopback = "loopback" in lower_name
        
        status = "Connected (Active)" if is_up else "Unplugged / No carrier"
        
        speed_label = f"{speed} Mbps"
        if speed >= 1000:
            speed_label = f"{round(speed/1000, 1)} Gbps"
            
        severity = "INFO"
        alert_msg = None
        
        # Check warnings/errors for wired interfaces
        if not is_loopback and not is_wireless:
            if not is_up:
                severity = "ERROR"
                alert_msg = f"Network cable unplugged on interface '{name}'."
            elif speed > 0 and speed < 1000:
                severity = "WARN"
                alert_msg = f"Wired port '{name}' negotiated at slow speed ({speed_label}). Bad cable or port port suspected."
                
        # Live traffic calculations
        bytes_sent = 0
        bytes_recv = 0
        tx_rate = 0.0  # KB/s
        rx_rate = 0.0  # KB/s
        
        if name in io_counters:
            nic_io = io_counters[name]
            bytes_sent = nic_io.bytes_sent
            bytes_recv = nic_io.bytes_recv
            
            if name in LAST_IO_STATS:
                last_sent, last_recv, last_t = LAST_IO_STATS[name]
                dt = current_time - last_t
                if dt > 0:
                    tx_rate = max(0.0, (bytes_sent - last_sent) / 1024 / dt)
                    rx_rate = max(0.0, (bytes_recv - last_recv) / 1024 / dt)
                    
            LAST_IO_STATS[name] = (bytes_sent, bytes_recv, current_time)
            
        # Speed bar percentage (relative to Gigabit 1000Mbps max baseline)
        max_speed = 1000.0
        if is_wireless:
            max_speed = 866.0 # standard ac/ax speed
        speed_pct = min(100.0, (speed / max_speed) * 100.0) if (is_up and speed > 0) else 0.0
        
        interfaces.append({
            "name": name,
            "ip": ip_addr,
            "mac": mac_addr,
            "status": status,
            "is_up": is_up,
            "speed": speed,
            "speed_label": speed_label,
            "speed_pct": speed_pct,
            "is_wireless": is_wireless,
            "is_loopback": is_loopback,
            "tx_rate": round(tx_rate, 2),
            "rx_rate": round(rx_rate, 2),
            "severity": severity,
            "alert": alert_msg
        })
        
    return interfaces

# --- FEATURE 2: Local Network IP Scanner ---
def get_local_subnet():
    # Attempt to find the local IPv4 address subnet (excluding loopbacks)
    addrs = psutil.net_if_addrs()
    for name, interfaces in addrs.items():
        # Skip loopbacks/virtual adapters
        if "loopback" in name.lower() or "vEthernet" in name:
            continue
        for addr in interfaces:
            if addr.family == socket.AF_INET and not addr.address.startswith("127."):
                parts = addr.address.split('.')
                if len(parts) == 4:
                    return f"{parts[0]}.{parts[1]}.{parts[2]}"
    return "192.168.1"  # Default fallback

def parse_arp_table():
    arp_entries = {}
    try:
        # Run arp -a on Windows
        output = subprocess.run(["arp", "-a"], capture_output=True, text=True, shell=True)
        lines = output.stdout.split('\n')
        
        # Regex matching Windows ARP output columns: IP, Physical Address, Type
        # e.g., "  192.168.1.1           00-11-22-33-44-55     dynamic"
        pattern = re.compile(r'\s*(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s+([0-9a-fA-F\-]{17})\s+(\w+)')
        
        for line in lines:
            match = pattern.match(line)
            if match:
                ip, mac, _type = match.groups()
                # Format MAC to standard colon separated uppercase
                mac_formatted = mac.replace('-', ':').upper()
                arp_entries[ip] = mac_formatted
    except Exception as e:
        print(f"Error parsing ARP table: {e}")
    return arp_entries

def ping_ip(ip):
    # Quick single packet ICMP ping with 200ms timeout
    try:
        # Windows command: ping -n 1 -w 200 IP
        result = subprocess.run(
            ["ping", "-n", "1", "-w", "200", ip],
            capture_output=True, text=True, shell=True
        )
        # Check return code or output content
        is_online = result.returncode == 0
        latency = 999.0
        
        if is_online:
            # Parse round trip time (e.g. "time=5ms" or "time<1ms")
            time_match = re.search(r'time[=<](\d+)ms', result.stdout)
            if time_match:
                latency = float(time_match.group(1))
            else:
                latency = 1.0  # minimal latency
        return ip, is_online, latency
    except:
        return ip, False, 999.0

def load_device_labels():
    ensure_config_dir()
    if os.path.exists(DEVICE_LABELS_FILE):
        try:
            with open(DEVICE_LABELS_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_device_label(ip, label):
    ensure_config_dir()
    labels = load_device_labels()
    labels[ip] = label
    with open(DEVICE_LABELS_FILE, 'w') as f:
        json.dump(labels, f, indent=4)

def scan_local_network():
    subnet = get_local_subnet()
    arp_table = parse_arp_table()
    custom_labels = load_device_labels()
    
    # Generate range of target IPs in subnet
    target_ips = [f"{subnet}.{i}" for i in range(1, 255)]
    
    results = []
    
    # Ping in parallel using ThreadPoolExecutor for speed
    with ThreadPoolExecutor(max_workers=64) as executor:
        futures = {executor.submit(ping_ip, ip): ip for ip in target_ips}
        for future in as_completed(futures):
            ip, is_online, latency = future.result()
            
            # Retrieve MAC if available in ARP table
            mac = arp_table.get(ip, "N/A")
            
            # If the device is not online AND not in ARP table, skip it to keep lists tidy
            if not is_online and mac == "N/A":
                continue
                
            # Get MAC Vendor prefix
            vendor = "Unknown"
            if mac != "N/A" and len(mac) >= 8:
                prefix = mac[:8].upper()
                vendor = MAC_VENDORS.get(prefix, "Unknown")
                
            # Automatic device labeling
            last_octet = ip.split('.')[-1]
            if last_octet == "1":
                auto_label = "Router / Gateway"
            elif ip == socket.gethostbyname(socket.gethostname()):
                auto_label = "Main Server PC"
            elif last_octet in ("50", "51", "52", "53"):
                auto_label = "Counter PC"
            elif "printer" in vendor.lower() or last_octet == "250":
                auto_label = "Printer"
            else:
                auto_label = "Unknown"
                
            # Apply user-saved custom label over auto label
            label = custom_labels.get(ip, auto_label)
            
            # Ping color coding
            ping_color = "green"
            if latency > 100:
                ping_color = "red"
            elif latency > 30:
                ping_color = "amber"
                
            results.append({
                "ip": ip,
                "mac": mac,
                "vendor": vendor,
                "label": label,
                "online": is_online,
                "latency": latency if is_online else "N/A",
                "ping_color": ping_color if is_online else "gray"
            })
            
    # Sort results by the numerical value of the fourth octet
    results.sort(key=lambda x: int(x["ip"].split('.')[-1]))
    global LAST_SCAN_RESULTS
    LAST_SCAN_RESULTS = results
    return results

def get_cached_scan_results():
    global LAST_SCAN_RESULTS
    if not LAST_SCAN_RESULTS:
        custom_labels = load_device_labels()
        results = []
        for ip, label in custom_labels.items():
            results.append({
                "ip": ip,
                "mac": "N/A",
                "vendor": "Unknown",
                "label": label,
                "online": False,
                "latency": "N/A",
                "ping_color": "gray"
            })
        return results
    return LAST_SCAN_RESULTS

# --- FEATURE 3: Live Traffic Graph Telemetry ---
def get_live_traffic():
    # Query system-wide I/O counters
    counters = psutil.net_io_counters()
    
    # Analyze active TCP connections to calculate protocol breakdown
    breakdown = {
        "Billing HTTP/S": 0,
        "Local Database": 0,
        "Cloud database": 0,
        "Other / Internet": 0
    }
    
    try:
        connections = psutil.net_connections(kind='tcp')
        for conn in connections:
            if conn.status == 'ESTABLISHED' and conn.raddr:
                rport = conn.raddr.port
                raddr_ip = conn.raddr.ip
                
                if rport in (80, 443):
                    if "supabase" in raddr_ip or "neon" in raddr_ip:
                        breakdown["Cloud database"] += 1
                    else:
                        breakdown["Billing HTTP/S"] += 1
                elif rport == 3306:
                    breakdown["Local Database"] += 1
                else:
                    breakdown["Other / Internet"] += 1
    except:
        pass
        
    # Standardize values for pie/donut chart
    total_conns = sum(breakdown.values())
    if total_conns == 0:
        breakdown = {
            "Billing HTTP/S": 40,
            "Local Database": 30,
            "Cloud database": 20,
            "Other / Internet": 10
        }
    else:
        for k in breakdown:
            breakdown[k] = int((breakdown[k] / total_conns) * 100)
            
    return {
        "bytes_sent": counters.bytes_sent,
        "bytes_recv": counters.bytes_recv,
        "timestamp": time.time(),
        "protocols": breakdown
    }

# --- FEATURE 4: Bandwidth Usage by Device (Socket connections) ---
def get_bandwidth_by_device():
    # On Windows, netstat -bn maps process executable names, which requires admin.
    # If not admin, we fall back to netstat -an which displays remote IP list without process names.
    devices_data = {}
    admin_active = is_admin()
    
    try:
        # Run netstat to get active TCP endpoints
        cmd = ["netstat", "-bn" if admin_active else "-an"]
        output = subprocess.run(cmd, capture_output=True, text=True, shell=True)
        lines = output.stdout.split('\n')
        
        current_process = "Unknown"
        for line in lines:
            line = line.strip()
            
            # If admin, netstat -b outputs executable name on the line below the connection
            # e.g., "  TCP    192.168.1.10:5004      192.168.1.50:52300     ESTABLISHED"
            #       "  [SagarBilling.exe]"
            if admin_active and line.startswith('[') and line.endswith(']'):
                current_process = line[1:-1]
                continue
                
            if "ESTABLISHED" in line:
                parts = re.split(r'\s+', line)
                if len(parts) >= 4:
                    remote_endpoint = parts[2]
                    # Extract remote IP address (split off port)
                    ip_match = re.match(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', remote_endpoint)
                    if ip_match:
                        remote_ip = ip_match.group(1)
                        if remote_ip != "127.0.0.1":
                            if remote_ip not in devices_data:
                                devices_data[remote_ip] = {"connections": 0, "process": "Unknown"}
                            devices_data[remote_ip]["connections"] += 1
                            if admin_active:
                                devices_data[remote_ip]["process"] = current_process
    except Exception as e:
        print(f"Error reading bandwidth sockets: {e}")
        
    # Convert active connections count to estimated traffic volume (MBs) for mock visual plotting
    results = []
    custom_labels = load_device_labels()
    
    for ip, info in devices_data.items():
        # Estimate bandwidth based on active sockets for layout representation
        mock_mb = info["connections"] * 3.5 
        
        # Tag alert if an unknown IP is pulling considerable connections/data
        alert = False
        label = custom_labels.get(ip, "Unknown")
        if label == "Unknown" and mock_mb > 10.0:
            alert = True
            
        results.append({
            "ip": ip,
            "label": label,
            "connections": info["connections"],
            "process": info["process"],
            "mb": round(mock_mb, 1),
            "alert": alert
        })
        
    results.sort(key=lambda x: x["mb"], reverse=True)
    return {
        "admin": admin_active,
        "devices": results
    }

# --- FEATURE 5: Port Scanner ---
def scan_single_port(ip, port):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.5)
        res = s.connect_ex((ip, port))
        s.close()
        return port, res == 0
    except:
        return port, False

def scan_ports(target_ip):
    target_ports = [21, 22, 23, 53, 80, 443, 445, 3306, 3389, 8080]
    results = []
    
    # Define expected open ports for internal billing systems
    expected_open = {
        80: "HTTP (Web App)",
        443: "HTTPS (Web App)",
        3306: "MySQL (Local Database)",
        8080: "Alternate HTTP"
    }
    
    # Threat levels for risky open ports
    risky_ports = {
        21: "FTP (Plaintext credentials risk)",
        23: "Telnet (Unencrypted credentials risk)",
        445: "SMB (Direct exploit target)",
        3389: "RDP (Brute force target)"
    }
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(scan_single_port, target_ip, p): p for p in target_ports}
        for future in as_completed(futures):
            port, is_open = future.result()
            
            status = "closed"
            security = "safe"
            label = expected_open.get(port, risky_ports.get(port, f"Port {port}"))
            
            if is_open:
                status = "open"
                if port in risky_ports:
                    security = "risky"
                elif port in expected_open:
                    security = "expected"
                else:
                    security = "warning"
                    
            results.append({
                "port": port,
                "label": label,
                "status": status,
                "security": security
            })
            
    results.sort(key=lambda x: x["port"])
    return results

# --- FEATURE 6: Alerts & Event Log ---
def load_alerts_log():
    ensure_config_dir()
    if os.path.exists(ALERTS_LOG_FILE):
        try:
            with open(ALERTS_LOG_FILE, 'r') as f:
                return json.load(f)
        except:
            return []
    return []

def save_alerts_log(alerts):
    ensure_config_dir()
    with open(ALERTS_LOG_FILE, 'w') as f:
        json.dump(alerts[:100], f, indent=4) # Limit log length to last 100 alerts

def generate_system_alerts(interfaces, scanned_ips, health_grid):
    ensure_config_dir()
    current_alerts = []
    timestamp = datetime_str = time.strftime("%Y-%m-%d %H:%M:%S")
    
    # 1. Check Interfaces
    for nic in interfaces:
        if nic["is_loopback"]:
            continue
        if not nic["is_up"]:
            current_alerts.append({
                "timestamp": timestamp,
                "severity": "ERROR",
                "source": nic["name"],
                "message": f"Network cable unplugged on interface '{nic['name']}'.",
                "action": "Ensure LAN cable is clicked securely into the port and the router is powered on."
            })
        elif not nic["is_wireless"] and nic["speed"] > 0 and nic["speed"] < 1000:
            current_alerts.append({
                "timestamp": timestamp,
                "severity": "WARN",
                "source": nic["name"],
                "message": f"Slow connection speed negotiated on '{nic['name']}' ({nic['speed_label']}).",
                "action": "Replace the Ethernet cable. Confirm router/switch supports Gigabit speed."
            })
            
    # 2. Check Gateway/DNS Health Check
    if health_grid.get("gateway") == "offline":
        current_alerts.append({
            "timestamp": timestamp,
            "severity": "ERROR",
            "source": "Default Gateway",
            "message": "Router offline - all client counters will lose connection.",
            "action": "Check if main router is turned off. Verify router LAN ports are active."
        })
    elif health_grid.get("dns_google") == "offline" and health_grid.get("dns_cloudflare") == "offline":
        current_alerts.append({
            "timestamp": timestamp,
            "severity": "WARN",
            "source": "DNS Services",
            "message": "DNS failure - local network is working, but internet is down.",
            "action": "Verify internet subscription status. Restart the ISP fiber/modem box."
        })
        
    # 3. Check for Offline known counters
    custom_labels = load_device_labels()
    # Collect IPs labeled as Counter PCs
    counter_ips = [ip for ip, label in custom_labels.items() if "counter" in label.lower()]
    scanned_ip_map = {item["ip"]: item for item in scanned_ips}
    
    for c_ip in counter_ips:
        if c_ip in scanned_ip_map:
            device = scanned_ip_map[c_ip]
            if not device["online"]:
                current_alerts.append({
                    "timestamp": timestamp,
                    "severity": "WARN",
                    "source": f"Counter ({c_ip})",
                    "message": f"Billing counter PC at {c_ip} went offline.",
                    "action": "Check if counter computer was shut down or disconnected from Wi-Fi."
                })
            elif device["latency"] != "N/A" and device["latency"] > 100:
                current_alerts.append({
                    "timestamp": timestamp,
                    "severity": "WARN",
                    "source": f"Counter ({c_ip})",
                    "message": f"High latency ping ({device['latency']}ms) on billing counter PC.",
                    "action": "Move the Wi-Fi router closer to the counter, or plug in LAN cable."
                })
                
    # 4. Check for unexpected unknown devices
    for device in scanned_ips:
        if device["label"] == "Unknown" and device["online"]:
            current_alerts.append({
                "timestamp": timestamp,
                "severity": "INFO",
                "source": device["ip"],
                "message": f"Unknown device connected to the network at {device['ip']}.",
                "action": "Identify the device. Right-click in scanner to assign a label or block on router."
            })
            
    # Merge current active alerts with log history
    saved_log = load_alerts_log()
    
    # Avoid duplicate active logs
    existing_messages = {item["message"] for item in saved_log[:15]}
    new_entries = []
    for alert in current_alerts:
        if alert["message"] not in existing_messages:
            new_entries.append(alert)
            
    if new_entries:
        merged_log = new_entries + saved_log
        save_alerts_log(merged_log)
        return new_entries + saved_log
        
    return saved_log

# --- FEATURE 7: Wi-Fi Signal Strength ---
def get_wifi_info():
    # Retrieve Wi-Fi statistics on Windows via netsh
    info = {
        "connected": False,
        "ssid": "N/A",
        "band": "N/A",
        "channel": "N/A",
        "signal": 0,
        "signal_dbm": -99,
        "signal_color": "gray",
        "rate_rx": "N/A",
        "rate_tx": "N/A"
    }
    
    try:
        output = subprocess.run(
            ["netsh", "wlan", "show", "interfaces"],
            capture_output=True, text=True, shell=True
        )
        lines = output.stdout.split('\n')
        
        for line in lines:
            line = line.strip()
            if ":" in line:
                key, val = line.split(":", 1)
                key = key.strip().lower()
                val = val.strip()
                
                if "state" in key and val == "connected":
                    info["connected"] = True
                elif "ssid" in key and "bssid" not in key:
                    info["ssid"] = val
                elif "channel" in key:
                    info["channel"] = val
                elif "signal" in key:
                    # e.g., "Signal                 : 85%"
                    pct_match = re.search(r'(\d+)', val)
                    if pct_match:
                        pct = int(pct_match.group(1))
                        info["signal"] = pct
                        
                        # Convert signal percentage to approximate dBm: dBm = (pct / 2) - 100
                        dbm = int((pct / 2) - 100)
                        info["signal_dbm"] = dbm
                        
                        # Signal quality classification
                        if dbm >= -60:
                            info["signal_color"] = "green"
                        elif dbm >= -70:
                            info["signal_color"] = "amber"
                        else:
                            info["signal_color"] = "red"
                elif "receive rate" in key:
                    info["rate_rx"] = val
                elif "transmit rate" in key:
                    info["rate_tx"] = val
                    
        # Determine frequency band based on channel number on Windows
        if info["connected"] and info["channel"] != "N/A":
            try:
                ch = int(info["channel"])
                info["band"] = "2.4 GHz" if ch <= 14 else "5.0 GHz"
            except:
                pass
    except Exception as e:
        print(f"Error parsing Wi-Fi stats: {e}")
        
    return info

# --- FEATURE 8: Gateway & DNS Health Check ---
def get_default_gateway_win():
    # Run route print to determine default route
    try:
        output = subprocess.run(["route", "print", "0.0.0.0"], capture_output=True, text=True, shell=True)
        lines = output.stdout.split('\n')
        for line in lines:
            line = line.strip()
            # Look for lines with default route configuration
            if line.startswith("0.0.0.0"):
                parts = re.split(r'\s+', line)
                if len(parts) >= 4:
                    gateway_ip = parts[2]
                    # Verify IP format
                    if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', gateway_ip):
                        return gateway_ip
    except:
        pass
    return "192.168.1.1"  # standard fallback

def check_dns_gateway_health():
    gateway = get_default_gateway_win()
    dns_google = "8.8.8.8"
    dns_cloudflare = "1.1.1.1"
    
    targets = {
        "gateway": gateway,
        "dns_google": dns_google,
        "dns_cloudflare": dns_cloudflare
    }
    
    health = {}
    
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(ping_ip, ip): key for key, ip in targets.items()}
        for future in as_completed(futures):
            key = futures[future]
            ip, is_online, latency = future.result()
            
            status = "online" if is_online else "offline"
            color = "green"
            if not is_online:
                color = "red"
            elif latency > 30:
                color = "amber"
                
            health[key] = status
            health[f"{key}_latency"] = f"{int(latency)} ms" if is_online else "N/A"
            health[f"{key}_color"] = color
            
    return health
