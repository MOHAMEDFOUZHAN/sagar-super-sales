-- Sagar Super Complete Database Schema for PostgreSQL / Supabase
-- Matches the active local Laragon MySQL schema exactly

-- 1. DROP EXISTING TABLES FOR CLEAN OVERWRITE (CASCADE handles constraints)
DROP TABLE IF EXISTS denominations CASCADE;
DROP TABLE IF EXISTS cash_balance CASCADE;
DROP TABLE IF EXISTS audit_logs CASCADE;
DROP TABLE IF EXISTS expenses CASCADE;
DROP TABLE IF EXISTS returns_log CASCADE;
DROP TABLE IF EXISTS stock_movements CASCADE;
DROP TABLE IF EXISTS bill_items CASCADE;
DROP TABLE IF EXISTS bill_sequences CASCADE;
DROP TABLE IF EXISTS bills CASCADE;
DROP TABLE IF EXISTS categories CASCADE;
DROP TABLE IF EXISTS products CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS account_entries CASCADE;
DROP TABLE IF EXISTS daily_position_list CASCADE;

-- 2. CREATE TABLES IN LOGICAL ORDER

-- Users Table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) DEFAULT 'sales',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Categories Table
CREATE TABLE IF NOT EXISTS categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE
);

-- Products Table
CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    barcode VARCHAR(100) UNIQUE,
    name VARCHAR(255) NOT NULL,
    category VARCHAR(100),
    price DECIMAL(10, 2) NOT NULL,
    bizz DECIMAL(10, 2) DEFAULT 0.00,
    current_stock INTEGER DEFAULT 0,
    min_threshold INTEGER DEFAULT 25,
    unit VARCHAR(20) DEFAULT 'PCS',
    expiry_date DATE,
    last_updated TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Bills Table
CREATE TABLE IF NOT EXISTS bills (
    id SERIAL PRIMARY KEY,
    invoice_no VARCHAR(20) UNIQUE,
    bill_date TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    total_amount DECIMAL(10, 2) NOT NULL,
    payment_mode VARCHAR(20) DEFAULT 'CASH',
    status VARCHAR(20) DEFAULT 'PAID',
    tsc_percent DECIMAL(5, 2) DEFAULT 0.00,
    tsc_amount DECIMAL(10, 2) DEFAULT 0.00,
    source_bill_id INTEGER,
    discount DECIMAL(10, 2) DEFAULT 0.00,
    created_by VARCHAR(50),
    prev_total DECIMAL(10, 2) DEFAULT 0.00,
    balance DECIMAL(10, 2) DEFAULT 0.00,
    client_request_id VARCHAR(64) UNIQUE
);

-- Bill Sequences Table
CREATE TABLE IF NOT EXISTS bill_sequences (
    seq_date DATE PRIMARY KEY,
    last_value INTEGER DEFAULT 0,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Bill Items Table
CREATE TABLE IF NOT EXISTS bill_items (
    id SERIAL PRIMARY KEY,
    bill_id INTEGER REFERENCES bills(id) ON DELETE CASCADE,
    product_id INTEGER,
    product_name VARCHAR(255),
    qty INTEGER,
    rate DECIMAL(10, 2),
    amount DECIMAL(10, 2),
    bizz_percent DECIMAL(10, 2) DEFAULT 0.00,
    bizz_amount DECIMAL(10, 2) DEFAULT 0.00,
    product_code VARCHAR(50)
);

-- Stock Movements Table
CREATE TABLE IF NOT EXISTS stock_movements (
    id SERIAL PRIMARY KEY,
    product_id INTEGER REFERENCES products(id),
    bill_id INTEGER REFERENCES bills(id) ON DELETE SET NULL,
    movement_type VARCHAR(30),
    qty_change DECIMAL(10, 2),
    stock_before DECIMAL(10, 2),
    stock_after DECIMAL(10, 2),
    created_by VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Returns Log Table
CREATE TABLE IF NOT EXISTS returns_log (
    id SERIAL PRIMARY KEY,
    bill_id INTEGER REFERENCES bills(id) ON DELETE CASCADE,
    product_name VARCHAR(255),
    qty DECIMAL(10, 2),
    amount DECIMAL(10, 2),
    reason VARCHAR(255),
    returned_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(50),
    status VARCHAR(50),
    action VARCHAR(50),
    product_code VARCHAR(50)
);

-- Expenses Table
CREATE TABLE IF NOT EXISTS expenses (
    id SERIAL PRIMARY KEY,
    category VARCHAR(100),
    description TEXT,
    amount DECIMAL(10, 2),
    expense_date TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    expense_group VARCHAR(20) DEFAULT 'OFFICE'
);

-- Audit Logs Table
CREATE TABLE IF NOT EXISTS audit_logs (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(50),
    action VARCHAR(255),
    table_name VARCHAR(50),
    record_id INTEGER,
    old_value TEXT,
    new_value TEXT,
    action_time TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Cash Balance Table
CREATE TABLE IF NOT EXISTS cash_balance (
    id SERIAL PRIMARY KEY,
    balance_date DATE UNIQUE,
    opening_balance DECIMAL(10, 2) DEFAULT 0.00,
    actual_closing DECIMAL(10, 2) DEFAULT 0.00,
    closing_balance DECIMAL(10, 2) DEFAULT 0.00,
    difference DECIMAL(10, 2) DEFAULT 0.00,
    status VARCHAR(20) DEFAULT 'OPEN',
    inflow DECIMAL(10, 2) DEFAULT 0.00
);

-- Denominations Table
CREATE TABLE IF NOT EXISTS denominations (
    id SERIAL PRIMARY KEY,
    balance_id INTEGER REFERENCES cash_balance(id) ON DELETE CASCADE,
    note_value INTEGER,
    count INTEGER DEFAULT 0
);

-- Account Entries Table
CREATE TABLE IF NOT EXISTS account_entries (
    id SERIAL PRIMARY KEY,
    entry_date TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    major_type VARCHAR(50) CHECK (major_type IN ('Asset','Liability','Equity','Revenue','Direct Expense','Operating Expense')),
    sub_type VARCHAR(100),
    description TEXT,
    amount DECIMAL(15, 2),
    payment_type VARCHAR(50) DEFAULT 'Cash' CHECK (payment_type IN ('Cash','UPI','Bank','Other')),
    created_by INTEGER
);

-- Daily Position List Table
CREATE TABLE IF NOT EXISTS daily_position_list (
    barcode VARCHAR(50) PRIMARY KEY
);

-- 3. CREATE PERFORMANCE INDEXES
CREATE INDEX IF NOT EXISTS idx_products_barcode ON products (barcode);
CREATE INDEX IF NOT EXISTS idx_products_name ON products (name);
CREATE INDEX IF NOT EXISTS idx_products_category ON products (category);

CREATE INDEX IF NOT EXISTS idx_bills_bill_date ON bills (bill_date);
CREATE INDEX IF NOT EXISTS idx_bills_created_by ON bills (created_by);
CREATE INDEX IF NOT EXISTS idx_bills_status ON bills (status);

CREATE INDEX IF NOT EXISTS idx_bill_items_product_code ON bill_items (product_code);
CREATE INDEX IF NOT EXISTS idx_bill_items_product_name ON bill_items (product_name);

CREATE INDEX IF NOT EXISTS idx_stock_movements_product_id ON stock_movements (product_id);
CREATE INDEX IF NOT EXISTS idx_stock_movements_bill_id ON stock_movements (bill_id);

CREATE INDEX IF NOT EXISTS idx_expenses_expense_date ON expenses (expense_date);
CREATE INDEX IF NOT EXISTS idx_expenses_category ON expenses (category);
