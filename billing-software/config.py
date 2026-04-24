import os
import json
import sys

class Config:
    # Default MySQL Configuration
    MYSQL_HOST = '192.168.1.12'
    MYSQL_USER = 'root'
    MYSQL_PASSWORD = ''  # Default for Laragon root is usually empty.
    MYSQL_DB = 'maple_pro_db'
    MYSQL_PORT = 3306
    MYSQL_POOL_NAME = 'maple_pool'
    MYSQL_POOL_SIZE = 10
    MYSQL_AUTOCOMMIT = False
    
    # Server Connection Configuration
    SERVER_HOST = '0.0.0.0' # Set to 0.0.0.0 to listen on all interfaces
    SERVER_PORT = 5004
    
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev_key_123')

    @classmethod
    def load_external_config(cls):
        """
        Smart configuration loader for Actual Project. 
        Searches multiple system paths and creates a tidy local 'Configuration' 
        folder if no existing config is found.
        """
        try:
            # 1. Determine base directory (handles PyInstaller EXE or raw script)
            if getattr(sys, 'frozen', False):
                base_dir = os.path.dirname(sys.executable)
            else:
                base_dir = os.path.dirname(os.path.abspath(__file__))

            # 2. Define the 'Tidy' local folder path
            local_config_dir = os.path.join(base_dir, "Configuration")
            local_config_file = os.path.join(local_config_dir, "config.json")

            # 3. List of paths to search (Priority order)
            search_paths = [
                local_config_file,                                     # App/Configuration/config.json
                os.path.join(base_dir, "config.json"),                 # Root of App folder
                os.path.join(os.path.expanduser("~"), "Documents", "SagarSoftware", "config.json"), # Documents
                os.path.join(os.environ.get('APPDATA', ''), "SagarSoftware", "config.json")          # AppData
            ]

            found_file = None
            for path in search_paths:
                if path and os.path.exists(path):
                    found_file = path
                    break

            # 4. If not found ANYWHERE, create the 'Configuration' folder and file locally
            if not found_file:
                if not os.path.exists(local_config_dir):
                    os.makedirs(local_config_dir)
                
                found_file = local_config_file
                sample_data = {
                    "MYSQL_HOST": cls.MYSQL_HOST,
                    "MYSQL_USER": cls.MYSQL_USER,
                    "MYSQL_PASSWORD": cls.MYSQL_PASSWORD,
                    "MYSQL_DB": cls.MYSQL_DB,
                    "MYSQL_PORT": cls.MYSQL_PORT,
                    "MYSQL_POOL_NAME": cls.MYSQL_POOL_NAME,
                    "MYSQL_POOL_SIZE": cls.MYSQL_POOL_SIZE,
                    "SERVER_HOST": cls.SERVER_HOST,
                    "SERVER_PORT": cls.SERVER_PORT
                }
                with open(found_file, 'w') as f:
                    json.dump(sample_data, f, indent=4)
                print(f"Created new configuration at: {found_file}")

            # 5. Apply the discovered/created settings to class memory
            if found_file:
                with open(found_file, 'r') as f:
                    data = json.load(f)
                    cls.MYSQL_HOST = data.get('MYSQL_HOST', cls.MYSQL_HOST)
                    cls.MYSQL_USER = data.get('MYSQL_USER', cls.MYSQL_USER)
                    cls.MYSQL_PASSWORD = data.get('MYSQL_PASSWORD', cls.MYSQL_PASSWORD)
                    cls.MYSQL_DB = data.get('MYSQL_DB', cls.MYSQL_DB)
                    cls.MYSQL_PORT = int(data.get('MYSQL_PORT', cls.MYSQL_PORT))
                    cls.MYSQL_POOL_NAME = data.get('MYSQL_POOL_NAME', cls.MYSQL_POOL_NAME)
                    cls.MYSQL_POOL_SIZE = int(data.get('MYSQL_POOL_SIZE', cls.MYSQL_POOL_SIZE))
                    cls.SERVER_HOST = data.get('SERVER_HOST', cls.SERVER_HOST)
                    cls.SERVER_PORT = int(data.get('SERVER_PORT', cls.SERVER_PORT))
                
                # Store the actual path used for other utilities to reference
                cls.ACTIVE_CONFIG_PATH = found_file
                    
        except Exception as e:
            print(f"Error loading external config: {e}")

# Load external settings when logic is imported
Config.load_external_config()

