from __future__ import annotations
from typing import Sequence
try:
    import win32print
    HAS_PRINTER_SUPPORT = True
except ImportError:
    win32print = None
    HAS_PRINTER_SUPPORT = False
import os
import sys

ESC = b"\x1b"
GS = b"\x1d"
INIT_PRINTER = ESC + b"@"
ALIGN_LEFT = ESC + b"a\x00"
ALIGN_CENTER = ESC + b"a\x01"
BOLD_ON = ESC + b"E\x01"
BOLD_OFF = ESC + b"E\x00"
FULL_CUT = GS + b"V\x00"

ENCODING = "cp1252"
FEED_LINES_BEFORE_CUT = 4

SHOP_NAME_LINES = ("SAGAR NILGIRI PRODUCTS", "SUPER")
SHOP_ADDRESS_LINES = ("36 COMMERCIAL ROAD, NEXT TO A2B RESTAURANT,", "OOTY - 643001")
SHOP_PHONE = "Ph: 9363596124"
SHOP_GSTIN = "GSTIN: 33ACMPC6407B1Z7"
SHOP_WEBSITE = "www.sagarnilgiriproducts.com"
SHOP_FOOTER_LINES = (
    "FIXED PRICE", "Sagar - Since 1964", "COMMITTED TO QUALITY",
    "SHOP ONLINE @", SHOP_WEBSITE, "*Thanks for shopping***Kindly Visit Again*",
    "No return no replacement",
    "CELEBRATING 60 YEARS OF TRUST"
)

def clean_text(text: str) -> str:
    if not text: return ""
    return str(text).replace("\u20B9", "Rs.")

def get_printer_name() -> str:
    if not HAS_PRINTER_SUPPORT:
        return None
    try:
        return win32print.GetDefaultPrinter()
    except:
        return None

def format_amount(value: float) -> str:
    return f"{value:.2f}"

def fit_text(value: str, width: int) -> str:
    value = str(value)
    if len(value) <= width: return value
    if width <= 3: return value[:width]
    return value[: width - 3] + "..."

def item_row(name: str, qty: float, rate: float, amount: float, width: int = 42) -> str:
    name_col = fit_text(name, 18)
    qty_col = f"{qty:g}" 
    rate_col = format_amount(rate)
    amount_col = format_amount(amount)
    row = f"{name_col:<18}{qty_col:>4}{rate_col:>10}{amount_col:>10}"
    return row[:width]

def centered_lines(lines: Sequence[str], width: int = 42) -> list[str]:
    return [fit_text(line, width).center(width) for line in lines]

def build_copy(
    items: list[dict], 
    bill_no: str,
    bill_date: str,
    bill_time: str,
    bill_type: str = "UPI",
    width: int = 42,
    is_short: bool = False,
) -> bytes:
    total = sum(float(item.get('amount', 0)) for item in items)
    total_text = format_amount(total)
    payload = bytearray()
    payload += INIT_PRINTER

    def emit(text: str) -> None:
        payload.extend((clean_text(text) + "\n").encode(ENCODING, errors="replace"))

    payload += ALIGN_CENTER + BOLD_ON
    for line in SHOP_NAME_LINES:
        emit(line.center(width))

    if not is_short:
        payload += BOLD_OFF
        for line in SHOP_ADDRESS_LINES:
            emit(line.center(width))
        payload += ALIGN_LEFT
        emit(f"{SHOP_PHONE:<24}{'Type: ' + bill_type:>18}"[:width])
        emit("." * width)
        emit(f"{SHOP_GSTIN:<24}{'Date: ' + bill_date:>18}"[:width])
        emit(f"{'Bill No: ' + bill_no:<24}{'Time: ' + bill_time:>18}"[:width])
    else:
        payload += ALIGN_LEFT
        emit(f"{'office purpose only':<24}{'Type: ' + bill_type:>18}"[:width])
        emit("." * width)
        emit(f"Date: {bill_date}")
        emit(f"{'Bill No: ' + bill_no:<24}{'Time: ' + bill_time:>18}"[:width])

    emit("." * width)
    payload += BOLD_ON
    emit(f"{'Product':<18}{'Qty':>4}{'Rate':>10}{'Amount':>10}")
    payload += BOLD_OFF
    emit("." * width)

    for item in items:
        name = item.get('name', 'Item')
        qty = float(item.get('qty', 0))
        rate = float(item.get('rate', 0))
        amt = float(item.get('amount', 0))
        emit(item_row(name, qty, rate, amt, width))

    emit("." * width)
    payload += ALIGN_CENTER + BOLD_ON
    emit(f"Total: {total_text}")
    payload += BOLD_OFF
    emit("(PRICES INCLUSIVE OF GST)")
    emit("." * width)

    payload += BOLD_ON
    emit(f"{bill_type}: {total_text}")
    payload += BOLD_OFF
    emit("(Rounded off to Nearest Rupees)")
    emit("." * width)

    emit("")
    payload += ALIGN_CENTER
    if not is_short:
        for line in SHOP_FOOTER_LINES:
            emit(line.center(width))
    else:
        payload += BOLD_ON
        emit("BILL COPY".center(width))
        payload += BOLD_OFF

    return bytes(payload)

def build_print_job(
    items: list[dict],
    bill_no: str,
    bill_date: str,
    bill_time: str,
    bill_type: str = "UPI",
    width: int = 42,
) -> bytes:
    customer_copy = build_copy(items, bill_no, bill_date, bill_time, bill_type, width, is_short=False)
    shop_copy = build_copy(items, bill_no, bill_date, bill_time, bill_type, width, is_short=True)
    feed = b"\n" * FEED_LINES_BEFORE_CUT
    
    # CUT IN MIDDLE as requested
    return customer_copy + feed + FULL_CUT + shop_copy + feed + FULL_CUT

def print_thermal_bill(items, bill_no, bill_date, bill_time, bill_type, width=42):
    try:
        if not HAS_PRINTER_SUPPORT: return False
        printer = get_printer_name()
        if not printer: return False
        
        data = build_print_job(items, bill_no, bill_date, bill_time, bill_type, width)
        handle = win32print.OpenPrinter(printer)
        try:
            win32print.StartDocPrinter(handle, 1, ("Thermal Bill", None, "RAW"))
            win32print.StartPagePrinter(handle)
            win32print.WritePrinter(handle, data)
            win32print.EndPagePrinter(handle)
            win32print.EndDocPrinter(handle)
        finally:
            win32print.ClosePrinter(handle)
        return True
    except Exception as e:
        print(f"Print error: {e}")
        return False

def build_closure_report(data: dict, width: int = 42) -> bytes:
    payload = bytearray()
    payload += INIT_PRINTER
    
    def emit(text: str):
        payload.extend((clean_text(text) + "\n").encode(ENCODING, errors="replace"))

    # Header
    payload += ALIGN_CENTER + BOLD_ON
    emit("SAGAR SUPER")
    emit("FINAL REPORT")
    counter_text = data.get('counter', '')
    if counter_text:
        emit(str(counter_text).upper())
    payload += BOLD_OFF
    emit(f"Date: {data.get('date', '')}")
    emit(f"Time: {data.get('time', '')}")
    emit(f"Report Date: {data.get('report_date', '')}")
    emit("-" * width)

    # Sales Summary
    payload += ALIGN_LEFT + BOLD_ON
    emit(f"{'DESCRIPTION':<24}{'AMOUNT':>18}")
    payload += BOLD_OFF
    emit("-" * width)
    emit(f"{'TOTAL SALES:':<24}{data.get('total_sales', '0.00'):>18}")
    emit("-" * width)

    # Payment Methods
    payload += BOLD_ON
    emit("PAYMENT METHOD")
    payload += BOLD_OFF
    for pm in data.get('payments', []):
        emit(f"{pm['label']:<24}{pm['val']:>18}")
    emit("-" * width)

    # Categories
    payload += BOLD_ON
    emit("CATEGORY")
    payload += BOLD_OFF
    for cat in data.get('categories', []):
        emit(f"{cat['label']:<24}{cat['val']:>18}")
    emit("-" * width)

    # Office Expenses
    office_exps = [e for e in data.get('office_expenses', []) if e.get('label') not in ['TSC', 'BIZ']]
    payload += BOLD_ON
    emit("OFFICE EXPENSE")
    payload += BOLD_OFF
    if office_exps:
        for e in office_exps:
            emit(f"{e.get('label', '') + ':':<24}{e.get('val', '0.00'):>18}")
    else:
        emit(f"{'NO OFFICE EXPENSE':<24}{'0.00':>18}")
    emit("-" * width)

    # Shop Expenses
    shop_exps = data.get('shop_expenses', [])
    payload += BOLD_ON
    emit("SHOP EXPENSE")
    payload += BOLD_OFF
    if shop_exps:
        for e in shop_exps:
            emit(f"{e.get('label', '') + ':':<24}{e.get('val', '0.00'):>18}")
    else:
        emit(f"{'NO SHOP EXPENSE':<24}{'0.00':>18}")
    emit("-" * width)

    # Bizz & TSC
    payload += BOLD_ON
    emit("BIZ & TSC SUMMARY")
    payload += BOLD_OFF
    emit(f"{'TotalBiz:':<24}{data.get('biz_total', '0.00'):>18}")
    emit(f"{'BIZ@80%:':<24}{data.get('biz80', '0.00'):>18}")
    emit(f"{'BIZ@20%:':<24}{data.get('biz20', '0.00'):>18}")
    emit(f"{'Total TSC:':<24}{data.get('tsc_total', '0.00'):>18}")
    emit(f"{'TSC@80%:':<24}{data.get('tsc80', '0.00'):>18}")
    emit(f"{'TSC@20%:':<24}{data.get('tsc20', '0.00'):>18}")
    emit("-" * width)

    # Cash Audit
    payload += BOLD_ON
    emit("CASH DEBIT EXPENSE")
    payload += BOLD_OFF
    try:
        expected_str = str(data.get('expected', '0.00')).replace('Rs.', '').replace('₹', '').replace(',', '').replace(' ', '').strip()
        expected_val = float(expected_str) if expected_str else 0.0
        ob_str = str(data.get('ob', '0.00')).replace('Rs.', '').replace('₹', '').replace(',', '').replace(' ', '').strip()
        ob_val = float(ob_str) if ob_str else 0.0
        counted_str = str(data.get('cb', '0.00')).replace('Rs.', '').replace('₹', '').replace(',', '').replace(' ', '').strip()
        counted_val = float(counted_str) if counted_str else 0.0
        
        actual_cb = counted_val + ob_val
        diff_val = actual_cb - expected_val
        diff_sign = "+" if diff_val >= 0 else "-"
        diff_str = f"Rs.{diff_sign}{abs(diff_val):,.2f}"
        cb_display = f"Rs.{actual_cb:,.2f}"
        cash_off_display = f"Rs.{counted_val:,.2f}"
    except Exception:
        diff_str = "Rs.0.00"
        cb_display = data.get('cb', '0.00')
        cash_off_display = data.get('cash_off', '0.00')

    emit(f"{'O.B:':<24}{data.get('ob', '0.00'):>18}")
    emit(f"{'(+/-):':<24}{diff_str:>18}")
    payload += BOLD_ON
    emit(f"{'C.B:':<24}{cb_display:>18}")
    emit(f"{'C @ OFF:':<24}{cash_off_display:>18}")
    payload += BOLD_OFF
    emit("-" * width)

    # Denominations
    payload += BOLD_ON
    emit("DENOMINATIONS")
    payload += BOLD_OFF
    for d in data.get('denominations', []):
        emit(f"{d['note'] + ' * ' + str(d['count']):<24}{d['total']:>18}")
    emit("-" * width)

    # Footer
    payload += ALIGN_CENTER + BOLD_ON
    emit("END OF REPORT")
    payload += BOLD_OFF
    emit("\n" * 5)
    payload += FULL_CUT
    
    return bytes(payload)

def print_closure_report(data, width=42):
    try:
        if not HAS_PRINTER_SUPPORT: return False
        printer = get_printer_name()
        if not printer: return False
        
        raw_data = build_closure_report(data, width)
        handle = win32print.OpenPrinter(printer)
        try:
            win32print.StartDocPrinter(handle, 1, ("Closure Report", None, "RAW"))
            win32print.StartPagePrinter(handle)
            win32print.WritePrinter(handle, raw_data)
            win32print.EndPagePrinter(handle)
            win32print.EndDocPrinter(handle)
        finally:
            win32print.ClosePrinter(handle)
        return True
    except Exception as e:
        print(f"Closure print error: {e}")
        return False
