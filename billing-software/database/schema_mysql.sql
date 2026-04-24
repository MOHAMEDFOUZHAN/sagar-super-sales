-- Sagar Super Database Schema
-- Last updated: 2026-02-03

CREATE DATABASE IF NOT EXISTS sagar_super_db;
USE sagar_super_db;

-- Users Table
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('admin', 'sales', 'account') DEFAULT 'sales',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Products Table
CREATE TABLE IF NOT EXISTS products (
    id INT AUTO_INCREMENT PRIMARY KEY,
    barcode VARCHAR(50) UNIQUE,
    name VARCHAR(100) NOT NULL,
    category VARCHAR(50),
    price DECIMAL(10, 2) NOT NULL,
    current_stock INT DEFAULT 0,
    unit VARCHAR(20) DEFAULT 'PCS',
    bizz DECIMAL(10, 2) DEFAULT 0.00,
    min_threshold INT DEFAULT 25,
    expiry_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX (barcode),
    INDEX (name),
    INDEX (category)
);

-- Categories Table
CREATE TABLE IF NOT EXISTS categories (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE
);

-- Bills Table
CREATE TABLE IF NOT EXISTS bills (
    id INT AUTO_INCREMENT PRIMARY KEY,
    invoice_no VARCHAR(20) UNIQUE,
    client_request_id VARCHAR(64) UNIQUE,
    bill_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    total_amount DECIMAL(10, 2) NOT NULL,
    payment_mode VARCHAR(20),
    status VARCHAR(20) DEFAULT 'Paid',
    tsc_percent DECIMAL(5, 2) DEFAULT 0.00,
    tsc_amount DECIMAL(10, 2) DEFAULT 0.00,
    discount DECIMAL(10, 2) DEFAULT 0.00,
    source_bill_id INT,
    prev_total DECIMAL(10, 2) DEFAULT 0.00,
    balance DECIMAL(10, 2) DEFAULT 0.00,
    created_by VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX (bill_date),
    INDEX (created_by),
    INDEX (status)
);

CREATE TABLE IF NOT EXISTS bill_sequences (
    seq_date DATE PRIMARY KEY,
    last_value INT NOT NULL DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Bill Items Table
CREATE TABLE IF NOT EXISTS bill_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    bill_id INT,
    product_code VARCHAR(50),
    product_name VARCHAR(100),
    qty DECIMAL(10, 2),
    rate DECIMAL(10, 2),
    amount DECIMAL(10, 2),
    bizz_percent DECIMAL(5, 2),
    bizz_amount DECIMAL(10, 2),
    INDEX (product_code),
    INDEX (product_name),
    FOREIGN KEY (bill_id) REFERENCES bills(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS stock_movements (
    id INT AUTO_INCREMENT PRIMARY KEY,
    product_id INT NOT NULL,
    bill_id INT,
    movement_type VARCHAR(30) NOT NULL,
    qty_change DECIMAL(10, 2) NOT NULL,
    stock_before DECIMAL(10, 2) NOT NULL,
    stock_after DECIMAL(10, 2) NOT NULL,
    created_by VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX (product_id),
    INDEX (bill_id),
    FOREIGN KEY (product_id) REFERENCES products(id),
    FOREIGN KEY (bill_id) REFERENCES bills(id) ON DELETE SET NULL
);

-- Returns Log Table
CREATE TABLE IF NOT EXISTS returns_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    bill_id INT,
    product_name VARCHAR(100),
    qty DECIMAL(10, 2),
    amount DECIMAL(10, 2),
    reason TEXT,
    product_code VARCHAR(50),
    status VARCHAR(50),
    action VARCHAR(50),
    created_by VARCHAR(50),
    return_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (bill_id) REFERENCES bills(id) ON DELETE CASCADE
);

-- Expenses Table
CREATE TABLE IF NOT EXISTS expenses (
    id INT AUTO_INCREMENT PRIMARY KEY,
    expense_date DATE,
    category VARCHAR(50),
    amount DECIMAL(10, 2),
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX (expense_date),
    INDEX (category)
);

-- Audit Logs Table for Accountability (Point 9)
CREATE TABLE IF NOT EXISTS audit_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(50),
    action VARCHAR(255),
    table_name VARCHAR(50),
    record_id INT,
    old_value TEXT,
    new_value TEXT,
    action_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Cash Balance Table
CREATE TABLE IF NOT EXISTS cash_balance (
    id INT AUTO_INCREMENT PRIMARY KEY,
    balance_date DATE UNIQUE,
    opening_balance DECIMAL(10, 2),
    closing_balance DECIMAL(10, 2),
    actual_closing DECIMAL(10, 2),
    difference DECIMAL(10, 2),
    status VARCHAR(20) DEFAULT 'CLOSED'
);

-- Denominations Table
CREATE TABLE IF NOT EXISTS denominations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    balance_id INT,
    note_value INT,
    count INT,
    FOREIGN KEY (balance_id) REFERENCES cash_balance(id) ON DELETE CASCADE
);

-- Default User IDs
INSERT IGNORE INTO users (username, password_hash, role) VALUES ('admin', 'admin123', 'admin');
INSERT IGNORE INTO users (username, password_hash, role) VALUES ('counter', '123', 'sales');
INSERT IGNORE INTO users (username, password_hash, role) VALUES ('counter1', '123', 'sales');
INSERT IGNORE INTO users (username, password_hash, role) VALUES ('counter2', '123', 'sales');
INSERT IGNORE INTO users (username, password_hash, role) VALUES ('counter3', '123', 'sales');
INSERT IGNORE INTO users (username, password_hash, role) VALUES ('counter4', '123', 'sales');
INSERT IGNORE INTO users (username, password_hash, role) VALUES ('accountant', 'account123', 'account');


