
ALTER TABLE bill_items ADD COLUMN product_id INT;
ALTER TABLE cash_balance ADD COLUMN inflow DECIMAL(10, 2) DEFAULT 0.00;
ALTER TABLE expenses ADD COLUMN expense_group VARCHAR(50);
ALTER TABLE products ADD COLUMN last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP;

CREATE TABLE IF NOT EXISTS account_entries (
    id INT AUTO_INCREMENT PRIMARY KEY,
    major_type VARCHAR(50),
    sub_type VARCHAR(50),
    description TEXT,
    amount DECIMAL(10, 2),
    payment_type VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS daily_position_list (
    barcode VARCHAR(50) PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS holidays (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100),
    date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS seasonal_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    year INT,
    month INT,
    category VARCHAR(50),
    multiplier DECIMAL(5, 2)
);

CREATE TABLE IF NOT EXISTS stock_transfers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    transfer_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    product_code VARCHAR(50),
    qty DECIMAL(10, 2),
    reason TEXT,
    transfer_type VARCHAR(10) DEFAULT 'OUT'
);

