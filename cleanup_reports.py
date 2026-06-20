import os
import re

dir_path = r'D:\Sales\billing-software\frontend\admin\reports'
files = [
    'billwise_reports.html', 'billwise_sales.html', 'bizz_reports.html',
    'cancelled_bills.html', 'cancelled_report.html', 'cash_balance.html',
    'category_reports.html', 'change_sales.html', 'correction_bills.html',
    'counter_sales.html', 'daily_position.html', 'daily_sales.html',
    'daily_stock.html', 'detail_sales.html', 'expense_reports.html',
    'final_report_admin.html', 'final_report.html', 'final_sales_report.html',
    'online_sales_invoices.html', 'online_sales_reports.html', 'online_sales.html',
    'payment_reports.html', 'product_reports.html', 'sales_report.html',
    'sales_reports.html', 'stock_reports.html', 'total_sales.html',
    'transfer_report.html'
]

def clean_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Remove internal @media print blocks
    # This regex matches @media print { ... } even with nested braces (one level)
    content = re.sub(r'@media print\s*\{[^{}]*(\{([^{}]*)\}[^{}]*)*\}', '', content, flags=re.DOTALL)

    # 2. Simplify .print-only-header
    # Try to find the report name first
    report_name_match = re.search(r'<div class="print-only-header">.*?<p[^>]*>(.*?)</p>', content, re.DOTALL)
    report_name = "[Report Name]"
    if report_name_match:
        report_name = report_name_match.group(1).strip()
        # Clean up tags if any
        report_name = re.sub(r'<.*?>', '', report_name)

    new_header = f'''<div class="print-only-header">
            <h1>SAGAR SUPER</h1>
            <p>{report_name}</p>
            <p id="printDateRange"></p>
        </div>'''
    
    content = re.sub(r'<div class="print-only-header">.*?</div>', new_header, content, count=1, flags=re.DOTALL)

    # 3. Remove redundant footer style blocks at the bottom
    content = re.sub(r'<style>\s*@media print\s*\{\s*\.dynamic-footer\s*\{\s*display:\s*none\s*!important;\s*\}\s*\}\s*</style>', '', content, flags=re.DOTALL)

    # 4. Remove inline padding/margin from glass-panel or main containers
    content = re.sub(r'class="glass-panel" style="padding: 20px;"', 'class="glass-panel"', content)
    content = re.sub(r'class="glass-panel" style="padding: 30px;"', 'class="glass-panel"', content)
    
    # 5. Ensure .print-only-header { display: none; } is in the head style block
    if '.print-only-header { display: none; }' not in content and '.print-only-header {display: none;}' not in content:
        # Insert before </style> in the first style block
        content = re.sub(r'(<style>.*?)(\s*</style>)', r'\1\n        .print-only-header { display: none; }\2', content, count=1, flags=re.DOTALL)

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Cleaned {file_path}")

for file in files:
    path = os.path.join(dir_path, file)
    if os.path.exists(path):
        try:
            clean_file(path)
        except Exception as e:
            print(f"Error cleaning {file}: {e}")
    else:
        print(f"File not found: {path}")
