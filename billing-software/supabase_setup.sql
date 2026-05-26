-- ==========================================================
-- SUPABASE (POSTGRESQL) SCHEMA AND DATA MIGRATION SCRIPT
-- Generated on: 2026-05-26
-- ==========================================================

SET session_replication_role = 'replica';

-- ----------------------------------------------------------
-- 1. CREATE TABLES (POSTGRESQL)
-- ----------------------------------------------------------

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) DEFAULT 'sales' CHECK (role IN ('admin', 'sales', 'account')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE IF NOT EXISTS categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE
);


CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    barcode VARCHAR(50) UNIQUE,
    name VARCHAR(100) NOT NULL,
    category VARCHAR(50),
    price DECIMAL(10, 2) NOT NULL,
    current_stock INTEGER DEFAULT 0,
    unit VARCHAR(20) DEFAULT 'PCS',
    bizz DECIMAL(10, 2) DEFAULT 0.00,
    min_threshold INTEGER DEFAULT 25,
    expiry_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_products_barcode ON products (barcode);
CREATE INDEX IF NOT EXISTS idx_products_name ON products (name);
CREATE INDEX IF NOT EXISTS idx_products_category ON products (category);


CREATE TABLE IF NOT EXISTS bills (
    id SERIAL PRIMARY KEY,
    invoice_no VARCHAR(20) UNIQUE,
    client_request_id VARCHAR(64) UNIQUE,
    bill_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    total_amount DECIMAL(10, 2) NOT NULL,
    payment_mode VARCHAR(20),
    status VARCHAR(20) DEFAULT 'Paid',
    tsc_percent DECIMAL(5, 2) DEFAULT 0.00,
    tsc_amount DECIMAL(10, 2) DEFAULT 0.00,
    discount DECIMAL(10, 2) DEFAULT 0.00,
    source_bill_id INTEGER,
    prev_total DECIMAL(10, 2) DEFAULT 0.00,
    balance DECIMAL(10, 2) DEFAULT 0.00,
    created_by VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_bills_bill_date ON bills (bill_date);
CREATE INDEX IF NOT EXISTS idx_bills_created_by ON bills (created_by);
CREATE INDEX IF NOT EXISTS idx_bills_status ON bills (status);


CREATE TABLE IF NOT EXISTS bill_sequences (
    seq_date DATE PRIMARY KEY,
    last_value INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE IF NOT EXISTS bill_items (
    id SERIAL PRIMARY KEY,
    bill_id INTEGER REFERENCES bills(id) ON DELETE CASCADE,
    product_code VARCHAR(50),
    product_name VARCHAR(100),
    qty DECIMAL(10, 2),
    rate DECIMAL(10, 2),
    amount DECIMAL(10, 2),
    bizz_percent DECIMAL(5, 2),
    bizz_amount DECIMAL(10, 2)
);
CREATE INDEX IF NOT EXISTS idx_bill_items_product_code ON bill_items (product_code);
CREATE INDEX IF NOT EXISTS idx_bill_items_product_name ON bill_items (product_name);


CREATE TABLE IF NOT EXISTS stock_movements (
    id SERIAL PRIMARY KEY,
    product_id INTEGER REFERENCES products(id),
    bill_id INTEGER REFERENCES bills(id) ON DELETE SET NULL,
    movement_type VARCHAR(30) NOT NULL,
    qty_change DECIMAL(10, 2) NOT NULL,
    stock_before DECIMAL(10, 2) NOT NULL,
    stock_after DECIMAL(10, 2) NOT NULL,
    created_by VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_stock_movements_product_id ON stock_movements (product_id);
CREATE INDEX IF NOT EXISTS idx_stock_movements_bill_id ON stock_movements (bill_id);


CREATE TABLE IF NOT EXISTS returns_log (
    id SERIAL PRIMARY KEY,
    bill_id INTEGER REFERENCES bills(id) ON DELETE CASCADE,
    product_name VARCHAR(100),
    qty DECIMAL(10, 2),
    amount DECIMAL(10, 2),
    reason TEXT,
    product_code VARCHAR(50),
    status VARCHAR(50),
    action VARCHAR(50),
    created_by VARCHAR(50),
    return_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE IF NOT EXISTS expenses (
    id SERIAL PRIMARY KEY,
    expense_date DATE,
    category VARCHAR(50),
    amount DECIMAL(10, 2),
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_expenses_expense_date ON expenses (expense_date);
CREATE INDEX IF NOT EXISTS idx_expenses_category ON expenses (category);


CREATE TABLE IF NOT EXISTS audit_logs (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(50),
    action VARCHAR(255),
    table_name VARCHAR(50),
    record_id INTEGER,
    old_value TEXT,
    new_value TEXT,
    action_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE IF NOT EXISTS cash_balance (
    id SERIAL PRIMARY KEY,
    balance_date DATE UNIQUE,
    opening_balance DECIMAL(10, 2),
    closing_balance DECIMAL(10, 2),
    actual_closing DECIMAL(10, 2),
    difference DECIMAL(10, 2),
    status VARCHAR(20) DEFAULT 'CLOSED'
);


CREATE TABLE IF NOT EXISTS denominations (
    id SERIAL PRIMARY KEY,
    balance_id INTEGER REFERENCES cash_balance(id) ON DELETE CASCADE,
    note_value INTEGER,
    count INTEGER
);

-- ----------------------------------------------------------
-- 2. INSERT CURRENT SYSTEM DATA
-- ----------------------------------------------------------
-- Data for table: users (8 rows)
INSERT INTO users (id, username, password_hash, role, created_at) VALUES (1, 'counter1', '123', 'sales', '2026-01-14 11:52:59') ON CONFLICT DO NOTHING;
INSERT INTO users (id, username, password_hash, role, created_at) VALUES (2, 'counter2', '123', 'sales', '2026-02-12 11:44:22') ON CONFLICT DO NOTHING;
INSERT INTO users (id, username, password_hash, role, created_at) VALUES (3, 'counter3', '123', 'sales', '2026-02-12 11:45:08') ON CONFLICT DO NOTHING;
INSERT INTO users (id, username, password_hash, role, created_at) VALUES (4, 'counter4', '123', 'sales', '2026-02-12 11:45:54') ON CONFLICT DO NOTHING;
INSERT INTO users (id, username, password_hash, role, created_at) VALUES (5, 'admin', '123', 'admin', '2026-01-14 11:52:59') ON CONFLICT DO NOTHING;
INSERT INTO users (id, username, password_hash, role, created_at) VALUES (6, 'fouzhan', '123', 'ai', '2026-01-28 18:21:57') ON CONFLICT DO NOTHING;
INSERT INTO users (id, username, password_hash, role, created_at) VALUES (7, 'accountant', 'account123', 'account', '2026-02-08 10:38:15') ON CONFLICT DO NOTHING;
INSERT INTO users (id, username, password_hash, role, created_at) VALUES (9, 'counter', '123', 'sales', '2026-04-14 14:26:25') ON CONFLICT DO NOTHING;

-- Table categories is currently empty.

-- Data for table: products (271 rows)
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (5, '1400', 'ROSE WATER-200 ML', 'AROMATICS & COSMETICS', '70.00', '0.00', 98, 25, 'PCS', NULL, '2026-04-16 23:38:07') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (6, '1445', 'SANDAL GEL', 'AROMATICS & COSMETICS', '140.00', '12.00', 100, 25, 'PCS', NULL, '2026-02-21 20:00:07') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (7, '1401', 'ROSE WATER-500 ML', 'AROMATICS & COSMETICS', '160.00', '10.00', 100, 25, 'PCS', NULL, '2026-02-21 20:00:09') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (8, '1446', 'ALOVERA GEL', 'AROMATICS & COSMETICS', '140.00', '12.00', 100, 25, 'PCS', NULL, '2026-02-21 20:00:11') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (9, '1402', 'HERBAL ROOTS', 'AROMATICS & COSMETICS', '140.00', '12.00', 100, 25, 'PCS', NULL, '2026-02-21 20:00:13') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (10, '1447', 'SANDAL POWDER', 'AROMATICS & COSMETICS', '160.00', '10.00', 100, 25, 'PCS', NULL, '2026-02-21 20:00:15') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (11, '1403', 'ROSEMAERY OIL -25 ML', 'AROMATICS & COSMETICS', '650.00', '25.00', 100, 25, 'PCS', NULL, '2026-02-21 20:00:17') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (12, '1448', 'JAVADU POWDER-25 G', 'AROMATICS & COSMETICS', '100.00', '5.00', 100, 25, 'PCS', NULL, '2026-02-21 20:00:19') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (13, '1405', 'ROSEMARY OIL-50 ML', 'AROMATICS & COSMETICS', '1300.00', '50.00', 100, 25, 'PCS', NULL, '2026-02-21 20:00:20') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (14, '1449', 'JAVADU POWDER-50 G', 'AROMATICS & COSMETICS', '200.00', '10.00', 100, 25, 'PCS', NULL, '2026-02-21 20:00:22') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (15, '1409', 'TEA TREE OIL-25 ML', 'AROMATICS & COSMETICS', '450.00', '25.00', 100, 25, 'PCS', NULL, '2026-02-21 20:00:24') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (16, '1410', 'TEA TREE OIL-50 ML', 'AROMATICS & COSMETICS', '900.00', '50.00', 100, 25, 'PCS', NULL, '2026-02-21 20:00:26') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (17, '1454', 'SAFFRON SANDAL 3IN 1', 'AROMATICS & COSMETICS', '225.00', '5.00', 100, 25, 'PCS', NULL, '2026-02-21 20:00:28') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (18, '1411', 'LAVENDER OIL-25 ML', 'AROMATICS & COSMETICS', '325.00', '15.00', 100, 25, 'PCS', NULL, '2026-02-21 20:28:00') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (19, '11412', 'LAVENDER OIL-50 ML', 'AROMATICS & COSMETICS', '650.00', '30.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:58') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (20, '11413', 'LAVENDER OIL-100 ML', 'AROMATICS & COSMETICS', '1250.00', '60.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:58') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (21, '11414', 'JASMINE OIL-25 ML', 'AROMATICS & COSMETICS', '325.00', '15.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:58') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (22, '11415', 'JASMINE OIL-50 ML', 'AROMATICS & COSMETICS', '650.00', '30.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:58') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (23, '11416', 'JASMINE OIL-100 ML', 'AROMATICS & COSMETICS', '1250.00', '60.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:58') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (24, '11417', 'ROSE OIL-25 ML', 'AROMATICS & COSMETICS', '325.00', '15.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:58') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (25, '11418', 'ROSE OIL-50 ML', 'AROMATICS & COSMETICS', '650.00', '30.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:58') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (26, '11419', 'ROSE OIL-100 ML', 'AROMATICS & COSMETICS', '1250.00', '60.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:58') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (27, '11424', 'SANDAL OIL (A)-25 ML', 'AROMATICS & COSMETICS', '380.00', '15.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:58') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (28, '11425', 'SANDAL OIL (A)-50 ML', 'AROMATICS & COSMETICS', '760.00', '30.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:58') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (29, '11426', 'SANDAL OIL (A)-100 ML', 'AROMATICS & COSMETICS', '1500.00', '60.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:58') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (30, '11427', 'JAVADU OIL-25 ML', 'AROMATICS & COSMETICS', '325.00', '15.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:58') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (31, '11428', 'CONE FLOOR WASH-500 ML', 'AROMATICS & COSMETICS', '210.00', '10.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:58') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (32, '11429', 'CONE FLOOR WASH-1 LTR', 'AROMATICS & COSMETICS', '410.00', '20.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:58') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (33, '11433', 'SANDAL BATHI-100 G', 'AROMATICS & COSMETICS', '70.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:58') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (34, '11434', 'SANDAL BATHI-200 G', 'AROMATICS & COSMETICS', '140.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:58') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (35, '11435', 'SANDAL BATHI-400 G', 'AROMATICS & COSMETICS', '280.00', '8.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:58') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (36, '11436', 'ROSE BATHI-100 G', 'AROMATICS & COSMETICS', '95.00', '7.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:58') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (37, '1437', 'JASMINE BATHI-100 G', 'AROMATICS & COSMETICS', '95.00', '7.00', 100, 25, 'PCS', NULL, '2026-02-21 20:00:01') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (38, '1438', 'JAVADU BATHI-100 G', 'AROMATICS & COSMETICS', '95.00', '7.00', 100, 25, 'PCS', NULL, '2026-02-21 19:59:49') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (39, '1483', '3 IN 1 BRINDAVAN SANDAL ZX', 'AROMATICS & COSMETICS', '225.00', '5.00', 2, 25, 'PCS', NULL, '2026-05-25 23:49:57') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (40, '1484', 'CAUVERY SANDAL (P.D) ZX', 'AROMATICS & COSMETICS', '190.00', '5.00', 100, 25, 'PCS', NULL, '2026-02-21 19:59:40') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (41, '1441', 'SANDAL PACK', 'AROMATICS & COSMETICS', '140.00', '12.00', 100, 25, 'PCS', NULL, '2026-02-21 19:59:35') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (42, '1442', 'CUCUMBER PACK', 'AROMATICS & COSMETICS', '140.00', '12.00', 99, 25, 'PCS', NULL, '2026-04-25 00:05:15') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (43, '1486', 'EUC SOAP NEW AX', 'AROMATICS & COSMETICS', '220.00', '5.00', 100, 25, 'PCS', NULL, '2026-02-21 19:59:27') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (44, '1443', 'ALOVERA PACK', 'AROMATICS & COSMETICS', '140.00', '12.00', 97, 25, 'PCS', NULL, '2026-05-25 14:03:05') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (45, '1444', 'SANDAL CREAM', 'AROMATICS & COSMETICS', '140.00', '12.00', 65, 25, 'PCS', NULL, '2026-05-25 14:03:05') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (46, '1700', 'ROASTED ALMOND', 'CHOCO- MRD & CFC', '1200.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:58') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (47, '1800', 'HAZELNUT', 'CHOCO- MRD & CFC', '1500.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:58') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (48, '1701', 'WHOLE CASHEW', 'CHOCO- MRD & CFC', '1200.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:58') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (49, '1802', 'CARAMEL', 'CHOCO- MRD & CFC', '1500.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:58') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (50, '1702', 'FRUIT & NUT', 'CHOCO- MRD & CFC', '1000.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:58') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (51, '1803', 'STRAWBERRY', 'CHOCO- MRD & CFC', '1300.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:58') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (52, '1703', 'NUT MILK', 'CHOCO- MRD & CFC', '1000.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:58') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (53, '1804', 'ORANGE', 'CHOCO- MRD & CFC', '1300.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:58') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (54, '1704', 'RUM & RAISIN', 'CHOCO- MRD & CFC', '1000.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:58') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (55, '1805', 'COFFEE', 'CHOCO- MRD & CFC', '1300.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:58') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (56, '1705', 'BUTTER SCOTCH', 'CHOCO- MRD & CFC', '1000.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:58') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (57, '1807', 'COCONUT', 'CHOCO- MRD & CFC', '1300.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:58') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (58, '1706', 'CRISPIES', 'CHOCO- MRD & CFC', '950.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:58') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (59, '1808', 'WHITE MOSAIC', 'CHOCO- MRD & CFC', '1500.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:58') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (60, '1707', 'PLAIN MILK', 'CHOCO- MRD & CFC', '900.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:58') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (61, '1809', 'ALMOND', 'CHOCO- MRD & CFC', '1500.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:58') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (62, '1708', 'WALNUT PRALINES', 'CHOCO- MRD & CFC', '1200.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (63, '1810', 'IRISH', 'CHOCO- MRD & CFC', '1200.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (64, '1709', 'DARK FANTASY', 'CHOCO- MRD & CFC', '1000.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (65, '1811', 'PEANUT', 'CHOCO- MRD & CFC', '1200.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (66, '1710', 'DARK STICK', 'CHOCO- MRD & CFC', '900.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (67, '1813', 'MILK TWIST', 'CHOCO- MRD & CFC', '1500.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (68, '1711', 'ALMOND DAZZLERS', 'CHOCO- MRD & CFC', '1200.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (69, '1814', 'BUTTER SCOTCH', 'CHOCO- MRD & CFC', '1200.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (70, '1712', 'CASHEW ROCKERS', 'CHOCO- MRD & CFC', '1200.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (71, '1818', 'RASPBERRY', 'CHOCO- MRD & CFC', '1500.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (72, '1713', 'SUGAR FREE', 'CHOCO- MRD & CFC', '1800.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (73, '1820', 'ASSORTED  CENTER FILLED  DELIGHT-250G', 'CHOCO- MRD & CFC', '350.00', '10.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (74, '1714', 'WHITE TOBBLER', 'CHOCO- MRD & CFC', '1200.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (75, '1821', 'CHOCO ALMOND NUTTIES-100G', 'CHOCO- MRD & CFC', '140.00', '5.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (76, '1715', 'MILKY MIST', 'CHOCO- MRD & CFC', '1000.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (77, '1822', 'CHOCO ALMOND NUTTIES-250G', 'CHOCO- MRD & CFC', '350.00', '20.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (78, '1716', 'STRAWBERRY SMASH', 'CHOCO- MRD & CFC', '1000.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (79, '1823', 'CHOCO HAZELNUT NUTTIES-100G', 'CHOCO- MRD & CFC', '140.00', '5.00', 104, 25, 'PCS', NULL, '2026-04-16 23:29:21') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (80, '1717', 'PINEAPPLE PUNCH', 'CHOCO- MRD & CFC', '1000.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (81, '1824', 'CHOCO HAZELNUT NUTTIES-250G', 'CHOCO- MRD & CFC', '350.00', '20.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (82, '1718', 'MANGO MELODY', 'CHOCO- MRD & CFC', '1000.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (83, '1825', 'CHOCO BUTTERSCOTCH NUTTIES-100G', 'CHOCO- MRD & CFC', '140.00', '5.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (84, '1719', 'PISTACHIO SWIRL', 'CHOCO- MRD & CFC', '1000.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (85, '1826', 'CHOCO BUTTERSCOTCH NUTTIES-250G', 'CHOCO- MRD & CFC', '350.00', '20.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (86, '1720', 'ORANGE BLOSSOM', 'CHOCO- MRD & CFC', '1000.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (87, '1827', 'TEDDY LOLIPOP', 'CHOCO- MRD & CFC', '20.00', '2.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (88, '1722', 'KRUSHERS CHOCO BOX – 250G', 'CHOCO- MRD & CFC', '200.00', '10.00', 96, 25, 'PCS', NULL, '2026-04-05 12:28:33') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (89, '1828', 'CHOCO LOLIPOP', 'CHOCO- MRD & CFC', '30.00', '3.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (90, '1723', 'KRUSHERS CHOCO BOX – 500G', 'CHOCO- MRD & CFC', '400.00', '20.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (91, '1830', 'CHOCO CASHEW NUTTIES-100G', 'CHOCO- MRD & CFC', '140.00', '5.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (92, '1726', 'FLAVOURED KRUSHERS – 250G', 'CHOCO- MRD & CFC', '220.00', '10.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (93, '1831', 'CHOCO CASHEW NUTTIES-250G', 'CHOCO- MRD & CFC', '350.00', '20.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (94, '1832', 'CHOCO CRISPIES NUTTIES-100G', 'CHOCO- MRD & CFC', '140.00', '5.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (95, '1833', 'CHOCO CRISPIES NUTTIES-250G', 'CHOCO- MRD & CFC', '350.00', '20.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (96, '1834', 'ASSORTED NUTTY DELIGHT-250G', 'CHOCO- MRD & CFC', '400.00', '20.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (97, '1835', 'CASHEW FUDGE', 'CHOCO- MRD & CFC', '0.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (98, '1836', 'ALMOND FUDGE', 'CHOCO- MRD & CFC', '0.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (99, '1837', 'CHOCOLATE FUDGE', 'CHOCO- MRD & CFC', '0.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (100, '1838', 'WALNUT FUDGE', 'CHOCO- MRD & CFC', '0.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (101, '1839', 'HAZELNUT FUDGE', 'CHOCO- MRD & CFC', '0.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (102, '1840', 'PISTACHIO FUDGE', 'CHOCO- MRD & CFC', '0.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (103, '1900', 'ORANGE – FRUIT JELLY', 'FRUIT JELLY & VARKEY', '750.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (104, '1950', 'VARKEY - BIG', 'FRUIT JELLY & VARKEY', '120.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (105, '1901', 'LITCHI – FRUIT JELLY', 'FRUIT JELLY & VARKEY', '750.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (106, '1951', 'VARKEY - SMALL', 'FRUIT JELLY & VARKEY', '120.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (107, '1902', 'BANANA – FRUIT JELLY', 'FRUIT JELLY & VARKEY', '750.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (108, '1903', 'STRAWBERRY – FRUIT JELLY', 'FRUIT JELLY & VARKEY', '750.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (109, '1904', 'GREEN APPLE – FRUIT JELLY', 'FRUIT JELLY & VARKEY', '750.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (110, '1905', 'PINE APPLE – FRUIT JELLY', 'FRUIT JELLY & VARKEY', '750.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (111, '1906', 'GAUVA – FRUIT JELLY', 'FRUIT JELLY & VARKEY', '750.00', '0.00', 105, 25, 'PCS', NULL, '2026-04-16 23:29:21') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (112, '1908', 'ASSORTED – FRUIT JELLY', 'FRUIT JELLY & VARKEY', '750.00', '0.00', 105, 25, 'PCS', NULL, '2026-04-16 23:29:21') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (113, '1909', 'FRUIT JELLY MIXED BOX – 200G', 'FRUIT JELLY & VARKEY', '145.00', '5.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (114, '1910', 'FRUIT JELLY MIXED BOX – 400G', 'FRUIT JELLY & VARKEY', '290.00', '15.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (115, '1100', 'EUC-OIL - 30', 'OILS', '80.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (116, '1144', 'ALMOND SAFFRON-OIL – 100', 'OILS', '190.00', '10.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (117, '1101', 'EUC-OIL - 60', 'OILS', '155.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (118, '1145', 'ALMOND SAFFRON-OIL – 200', 'OILS', '380.00', '20.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (119, '1102', 'EUC-OIL - 100', 'OILS', '260.00', '4.00', 101, 25, 'PCS', NULL, '2026-02-05 17:20:12') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (120, '1146', 'ALMOND SAFFRON-OIL – 500', 'OILS', '950.00', '50.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (121, '1103', 'EUC-OIL - 200', 'OILS', '510.00', '8.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (122, '1104', 'EUC-OIL - 500', 'OILS', '1250.00', '20.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (123, '1105', 'EUC-OIL - 1 LTR', 'OILS', '2400.00', '50.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (124, '1106', 'W.G-OIL – 60', 'OILS', '130.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (125, '1150', 'EUC-OIL – 10', 'OILS', '60.00', '4.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (126, '1107', 'W.G-OIL – 100', 'OILS', '220.00', '5.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (127, '1151', 'HEENA-OIL – 10', 'OILS', '70.00', '4.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (128, '1108', 'W.G-OIL – 200', 'OILS', '440.00', '10.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (129, '1152', 'W.G-OIL – 10', 'OILS', '60.00', '4.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (130, '1109', 'W.G-OIL –500', 'OILS', '1050.00', '25.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (131, '1153', 'L.G-OIL – 10', 'OILS', '70.00', '4.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (132, '1110', 'W.G-OIL –1LTR', 'OILS', '2100.00', '50.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (133, '1154', 'CAMPHOR-OIL – 10', 'OILS', '50.00', '4.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (134, '1111', 'L.G-OIL – 60', 'OILS', '175.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (135, '1112', 'L.G-OIL – 100', 'OILS', '290.00', '5.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (136, '1113', 'L.G-OIL – 200', 'OILS', '580.00', '12.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (137, '1114', 'L.G-OIL – 500', 'OILS', '1450.00', '30.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (138, '1115', 'CAMPHOR-OIL - 60', 'OILS', '55.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (139, '1116', 'CAMPHOR-OIL – 100', 'OILS', '85.00', '8.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (140, '1117', 'CAMPHOR-OIL – 200', 'OILS', '160.00', '15.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (141, '1118', 'CAMPHOR-OIL – 500', 'OILS', '400.00', '40.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (142, '1119', 'CLOVE-OIL -30', 'OILS', '60.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (143, '1120', 'CLOVE-OIL -60', 'OILS', '120.00', '6.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (144, '1121', 'CLOVE-OIL -100', 'OILS', '200.00', '10.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (145, '1122', 'CLOVE-OIL -200', 'OILS', '400.00', '20.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (146, '1123', 'CITRIDORA-OIL - 60', 'OILS', '175.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (147, '1124', 'CITRIDORA-OIL – 100', 'OILS', '290.00', '10.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (148, '1125', 'CITRIDORA-OIL – 200', 'OILS', '580.00', '20.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (149, '1126', 'CITRIDORA-OIL – 500', 'OILS', '1450.00', '50.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (150, '1127', 'JAVA CITRONELLA-OIL - 60', 'OILS', '132.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (151, '1128', 'JAVA CITRONELLA-OIL – 100', 'OILS', '220.00', '7.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (152, '1129', 'JAVA CITRONELLA-OIL – 200', 'OILS', '440.00', '14.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (153, '1130', 'JAVA CITRONELLA-OIL – 500', 'OILS', '1100.00', '30.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (154, '1131', 'HEENA-OIL - 60', 'OILS', '200.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (155, '1132', 'HEENA-OIL – 100', 'OILS', '350.00', '7.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (156, '1133', 'HEENA-OIL – 200', 'OILS', '675.00', '15.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (157, '1134', 'HEENA-OIL – 500', 'OILS', '1650.00', '35.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (158, '1135', 'ALMOND-OIL - 60', 'OILS', '100.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (159, '1136', 'ALMOND-OIL – 100', 'OILS', '160.00', '8.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (160, '1137', 'ALMOND-OIL – 200', 'OILS', '320.00', '16.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (161, '1138', 'ALMOND-OIL – 500', 'OILS', '800.00', '40.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (162, '1139', 'OLIVE-OIL – 60', 'OILS', '65.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (163, '1140', 'OLIVE-OIL – 100', 'OILS', '95.00', '5.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (164, '1141', 'OLIVE-OIL – 200', 'OILS', '190.00', '10.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (165, '1142', 'OLIVE-OIL – 500', 'OILS', '460.00', '25.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (166, '1143', 'ALMOND SAFFRON-OIL - 60', 'OILS', '110.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (167, '1600', 'JOUJOUPS – 250G', 'OTHERS', '75.00', '5.00', 99, 25, 'PCS', NULL, '2026-02-05 17:20:21') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (168, '1602', 'SLIMMER HONEY – 500G', 'OTHERS', '300.00', '15.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (169, '1603', 'SLIMMER HONEY – 1KG', 'OTHERS', '600.00', '30.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (170, '1604', 'SAGAR HONEY – 500G', 'OTHERS', '240.00', '10.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (171, '1605', 'SAGAR HONEY – 1KG', 'OTHERS', '480.00', '20.00', 99, 25, 'PCS', NULL, '2026-02-05 17:20:21') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (172, '1606', 'MARSHMELLOW', 'OTHERS', '60.00', '3.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (173, '1610', 'FORTUNE WATER – 5L', 'OTHERS', '70.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (174, '1611', 'FAUCET CAP FORTUNE WATER – 5L', 'OTHERS', '80.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (175, '1612', 'BISLERI – 5L', 'OTHERS', '70.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (176, '1613', 'REDWINE – FREDI MONT', 'OTHERS', '700.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (177, '1614', 'RED WINE - VENETO', 'OTHERS', '600.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (178, '1615', 'VENETO RED WINE - NEW', 'OTHERS', '700.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (179, '1617', 'RED WINE – SENES', 'OTHERS', '500.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (180, '1620', 'REDWINE – VEGA RICA', 'OTHERS', '400.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (181, '1621', 'REDWINE – CARL JUNG', 'OTHERS', '400.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (182, '1622', 'WHITE WINE – CARL JUNG', 'OTHERS', '400.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (183, '1623', 'FORTUNE WATER 750ML', 'OTHERS', '60.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (184, '1624', 'WHITE WINE – BILLABONG', 'OTHERS', '700.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (185, '1654', 'PACKING BOX 100G', 'OTHERS', '0.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (186, '1655', 'PACKIBG BOX – 250G', 'OTHERS', '0.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (187, '1656', 'PACKING BOX – 500G', 'OTHERS', '0.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (188, '1660', 'FREE CARRY BAG - SMALL', 'OTHERS', '0.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (189, '1661', 'FREE CARRY BAG – MEDIUM', 'OTHERS', '0.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (190, '1662', 'FREE CARRY BAG - BAG', 'OTHERS', '0.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (191, '1200', 'CARDAMOM (A) 100G', 'SPICES', '480.00', '5.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (192, '1244', 'STAR ANISE-50G', 'SPICES', '70.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (193, '1201', 'CARDAMOM (A) 250G', 'SPICES', '1200.00', '15.00', 99, 25, 'PCS', NULL, '2026-02-05 17:20:21') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (194, '1202', 'CARDAMOM (B) 100G', 'SPICES', '0.00', '4.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (195, '1203', 'CARDAMOM (B) 250G', 'SPICES', '0.00', '10.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (196, '1204', 'CLOVES (A) 100G', 'SPICES', '200.00', '5.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (197, '1205', 'CLOVES (A) 250G', 'SPICES', '500.00', '15.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (198, '1206', 'CINNAMON-100G', 'SPICES', '60.00', '3.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (199, '1207', 'CINNAMON-250G', 'SPICES', '150.00', '8.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (200, '1208', 'STAR ANISE-100G', 'SPICES', '140.00', '4.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (201, '1252', 'SAFFRON-0.5 GRM', 'SPICES', '190.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (202, '1209', 'STAR ANISE-250G', 'SPICES', '350.00', '8.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (203, '1253', 'SAFFRON (A)-1 GRM', 'SPICES', '380.00', '15.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (204, '1210', 'DRY GINGER-100G', 'SPICES', '90.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (205, '1254', 'SAFFRON(A)-2 GRM', 'SPICES', '750.00', '30.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (206, '1211', 'DRY GINGER-250G', 'SPICES', '225.00', '8.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (207, '1212', 'MACE (A) 50G', 'SPICES', '260.00', '5.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (208, '1213', 'MACE (A) 100G', 'SPICES', '520.00', '10.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (209, '1214', 'SOMBU-250G', 'SPICES', '90.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (210, '1215', 'CINNAMON ROLL-100G', 'SPICES', '250.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (211, '1216', 'NUTMEG (A) 100G', 'SPICES', '170.00', '15.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (212, '1217', 'MASALA CARDAMOM-100G', 'SPICES', '360.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (213, '1218', 'MARATHI MOOKU-100G', 'SPICES', '60.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (214, '1219', 'KHUS KHUS-250G', 'SPICES', '500.00', '7.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (215, '1220', 'JEERA-250G', 'SPICES', '150.00', '7.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (216, '1221', 'SHAH JEERA-250G', 'SPICES', '225.00', '5.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (217, '1222', 'WHITE PEPPER-250G', 'SPICES', '500.00', '5.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (218, '1223', 'BAY LEAF', 'SPICES', '25.00', '8.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (219, '1224', 'BLACK PEPPER-100G', 'SPICES', '120.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (220, '1225', 'BLACK PEPPER-250G', 'SPICES', '300.00', '7.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (221, '1226', 'WHITE PEPPER-100G', 'SPICES', '180.00', '3.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (222, '1227', 'SHAH JEERA-100G', 'SPICES', '90.00', '3.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (223, '1228', 'KHUS KHUS-100G', 'SPICES', '200.00', '3.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (224, '1229', 'CARDAMOM (A) 50G', 'SPICES', '240.00', '3.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (225, '1230', 'CLOVES (A) 50G', 'SPICES', '100.00', '3.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (226, '1231', 'KALPASI-50G', 'SPICES', '50.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (227, '1232', 'KASRI METHI-50G', 'SPICES', '35.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (228, '1233', 'BLACK JEERA-100G', 'SPICES', '60.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (229, '1234', 'ROSE PETALS-50G', 'SPICES', '100.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (230, '1235', 'MIXED SPICES SMALL', 'SPICES', '250.00', '7.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (231, '1236', 'MIXED SPICES BIG', 'SPICES', '500.00', '14.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (232, '1237', 'SPICE TOUCH', 'SPICES', '520.00', '20.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (233, '1238', 'RAISIN-250G', 'SPICES', '160.00', '5.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (234, '1239', 'CHERRY-250G', 'SPICES', '80.00', '5.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (235, '1240', 'GINGER CANDY', 'SPICES', '95.00', '5.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (236, '1241', 'AMLA CANDY', 'SPICES', '60.00', '5.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (237, '1242', 'VANILLA POD', 'SPICES', '390.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (238, '1243', 'VANILLA EXTRACT', 'SPICES', '450.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (239, '1300', 'C.T.C TEA BOX 250 - GMS', 'TEA&COFFEE', '110.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (240, '1301', 'C.T.C TEA BOX 500 - GMS', 'TEA&COFFEE', '220.00', '5.00', 99, 25, 'PCS', NULL, '2026-02-05 17:20:21') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (241, '1302', 'DUST TEA BOX 250 - GMS', 'TEA&COFFEE', '110.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (242, '1303', 'DUST TEA BOX 500 - GMS', 'TEA&COFFEE', '220.00', '5.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (243, '1304', 'MASALA TEA BOX 250 - GMS', 'TEA&COFFEE', '120.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (244, '1305', 'MASALA TEA BOX 500 - GMS', 'TEA&COFFEE', '240.00', '7.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (245, '1306', 'CARDAMOM TEA BOX 250 - GMS', 'TEA&COFFEE', '120.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (246, '1307', 'CARDAMOM TEA BOX 500 - GMS', 'TEA&COFFEE', '240.00', '7.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (247, '1350', 'MORNING STAR COFFEE', 'TEA&COFFEE', '325.00', '10.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (248, '1308', 'COCOA TEA BOX 250 - GMS', 'TEA&COFFEE', '120.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (249, '1351', 'COFFEE COUNTRY SMALL', 'TEA&COFFEE', '260.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (250, '1309', 'COCOA TEA BOX 500 - GMS', 'TEA&COFFEE', '240.00', '7.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (251, '1352', 'COFFEE COUNTRY BIG', 'TEA&COFFEE', '520.00', '15.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (252, '1310', 'LEMON  TEA BOX 250 - GMS', 'TEA&COFFEE', '120.00', '0.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (253, '1311', 'LEMON  TEA BOX 500 - GMS', 'TEA&COFFEE', '240.00', '7.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (254, '1354', 'SIDHI INSTANT COFFEE-BIG', 'TEA&COFFEE', '400.00', '10.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (255, '1312', 'GINGER  TEA BOX 250 - GMS', 'TEA&COFFEE', '120.00', '4.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (256, '1313', 'VANILLA  TEA BOX 250 - GMS', 'TEA&COFFEE', '120.00', '4.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (257, '1314', 'SAGAR TEA – 250GMS', 'TEA&COFFEE', '190.00', '10.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (258, '1315', 'SAGAR TEA – 500 - GMS', 'TEA&COFFEE', '380.00', '20.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (259, '1316', 'GREEN TEA BOX 250 - GMS', 'TEA&COFFEE', '220.00', '10.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (260, '1359', 'SIDHI INSTANT-SMALL-NEW', 'TEA&COFFEE', '100.00', '7.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (261, '1317', 'GREEN TEA BOX 500 - GMS', 'TEA&COFFEE', '440.00', '20.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (262, '1318', 'C.T.C TEA JAR 1 KG', 'TEA&COFFEE', '400.00', '15.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (263, '1319', 'DUST TEA JAR 1 KG', 'TEA&COFFEE', '400.00', '15.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (264, '1320', 'MASALA TEA JAR 1 KG', 'TEA&COFFEE', '400.00', '15.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (265, '1321', 'CARDAMOM TEA JAR 1 KG', 'TEA&COFFEE', '400.00', '15.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (266, '1322', 'COCOA TEA JAR 1 KG', 'TEA&COFFEE', '400.00', '15.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (267, '1325', 'POUCH NILGIRIS TEA-100', 'TEA&COFFEE', '190.00', '10.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (268, '1326', 'POUCH GREEN TEA-100', 'TEA&COFFEE', '190.00', '10.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (269, '1327', 'POUCH GINGER TEA-100', 'TEA&COFFEE', '190.00', '10.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (270, '1328', 'POUCH MASALA TEA-100', 'TEA&COFFEE', '190.00', '10.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (271, '1329', 'POUCH CARDAMOM TEA-100', 'TEA&COFFEE', '0.00', '10.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (272, '1330', 'GOLDEN TIPS TEA 100', 'TEA&COFFEE', '210.00', '10.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (273, '1331', 'SILVER TIPS TEA-100', 'TEA&COFFEE', '210.00', '10.00', 100, 25, 'PCS', NULL, '2026-01-14 11:57:59') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (274, '1333', '5 IN 1 TEA 500 – GMS', 'TEA&COFFEE', '250.00', '10.00', 94, 25, 'PCS', NULL, '2026-04-16 23:38:07') ON CONFLICT DO NOTHING;
INSERT INTO products (id, barcode, name, category, price, bizz, current_stock, min_threshold, unit, expiry_date, last_updated) VALUES (275, '1999', 'test gram coco', 'General', '1.00', '0.00', 1100, 25, 'GM', NULL, '2026-04-30 22:46:07') ON CONFLICT DO NOTHING;

-- Data for table: bills (14 rows)
INSERT INTO bills (id, invoice_no, bill_date, total_amount, payment_mode, status, tsc_percent, tsc_amount, source_bill_id, discount, created_by, prev_total, balance, client_request_id) VALUES (1, '00001', '2026-04-24 15:35:41', '140.00', 'CASH', 'PAID', '0.00', '0.00', NULL, '0.00', 'counter1', '0.00', '0.00', NULL) ON CONFLICT DO NOTHING;
INSERT INTO bills (id, invoice_no, bill_date, total_amount, payment_mode, status, tsc_percent, tsc_amount, source_bill_id, discount, created_by, prev_total, balance, client_request_id) VALUES (2, '00002', '2026-04-24 16:42:01', '140.00', 'CASH', 'PAID', '0.00', '0.00', NULL, '0.00', 'counter1', '0.00', '0.00', NULL) ON CONFLICT DO NOTHING;
INSERT INTO bills (id, invoice_no, bill_date, total_amount, payment_mode, status, tsc_percent, tsc_amount, source_bill_id, discount, created_by, prev_total, balance, client_request_id) VALUES (3, '00003', '2026-04-24 16:44:13', '140.00', 'CASH', 'PAID', '0.00', '0.00', NULL, '0.00', 'counter1', '0.00', '0.00', NULL) ON CONFLICT DO NOTHING;
INSERT INTO bills (id, invoice_no, bill_date, total_amount, payment_mode, status, tsc_percent, tsc_amount, source_bill_id, discount, created_by, prev_total, balance, client_request_id) VALUES (4, '00004', '2026-04-25 00:05:15', '280.00', 'CASH', 'PAID', '0.00', '0.00', NULL, '0.00', 'counter1', '0.00', '0.00', NULL) ON CONFLICT DO NOTHING;
INSERT INTO bills (id, invoice_no, bill_date, total_amount, payment_mode, status, tsc_percent, tsc_amount, source_bill_id, discount, created_by, prev_total, balance, client_request_id) VALUES (5, 'INV-20260425-001', '2026-04-25 12:27:57', '140.00', 'Cash', 'Paid', '0.00', '0.00', NULL, '0.00', 'counter1', '0.00', '0.00', NULL) ON CONFLICT DO NOTHING;
INSERT INTO bills (id, invoice_no, bill_date, total_amount, payment_mode, status, tsc_percent, tsc_amount, source_bill_id, discount, created_by, prev_total, balance, client_request_id) VALUES (6, 'INV-20260425-002', '2026-04-25 12:27:57', '420.00', 'UPI', 'Paid', '0.00', '0.00', NULL, '0.00', 'counter1', '0.00', '0.00', NULL) ON CONFLICT DO NOTHING;
INSERT INTO bills (id, invoice_no, bill_date, total_amount, payment_mode, status, tsc_percent, tsc_amount, source_bill_id, discount, created_by, prev_total, balance, client_request_id) VALUES (7, '00005', '2026-04-27 15:18:18', '140.00', 'CASH', 'PAID', '0.00', '0.00', NULL, '0.00', 'counter1', '0.00', '0.00', NULL) ON CONFLICT DO NOTHING;
INSERT INTO bills (id, invoice_no, bill_date, total_amount, payment_mode, status, tsc_percent, tsc_amount, source_bill_id, discount, created_by, prev_total, balance, client_request_id) VALUES (8, '00006', '2026-04-27 15:18:35', '140.00', 'CASH', 'PAID', '0.00', '0.00', NULL, '0.00', 'counter1', '0.00', '0.00', NULL) ON CONFLICT DO NOTHING;
INSERT INTO bills (id, invoice_no, bill_date, total_amount, payment_mode, status, tsc_percent, tsc_amount, source_bill_id, discount, created_by, prev_total, balance, client_request_id) VALUES (9, '00007', '2026-04-29 12:50:38', '140.00', 'CASH', 'PAID', '0.00', '0.00', NULL, '0.00', 'counter1', '0.00', '0.00', NULL) ON CONFLICT DO NOTHING;
INSERT INTO bills (id, invoice_no, bill_date, total_amount, payment_mode, status, tsc_percent, tsc_amount, source_bill_id, discount, created_by, prev_total, balance, client_request_id) VALUES (10, '00008', '2026-04-29 12:51:36', '250.00', 'CASH', 'PAID', '0.00', '0.00', NULL, '0.00', 'counter1', '0.00', '0.00', NULL) ON CONFLICT DO NOTHING;
INSERT INTO bills (id, invoice_no, bill_date, total_amount, payment_mode, status, tsc_percent, tsc_amount, source_bill_id, discount, created_by, prev_total, balance, client_request_id) VALUES (11, '00009', '2026-05-04 17:19:54', '280.00', 'CASH', 'PAID', '0.00', '0.00', NULL, '0.00', 'counter1', '0.00', '0.00', NULL) ON CONFLICT DO NOTHING;
INSERT INTO bills (id, invoice_no, bill_date, total_amount, payment_mode, status, tsc_percent, tsc_amount, source_bill_id, discount, created_by, prev_total, balance, client_request_id) VALUES (12, '00010', '2026-05-04 17:23:26', '140.00', 'CREDIT', 'PAID', '0.00', '0.00', NULL, '0.00', 'counter1', '0.00', '0.00', NULL) ON CONFLICT DO NOTHING;
INSERT INTO bills (id, invoice_no, bill_date, total_amount, payment_mode, status, tsc_percent, tsc_amount, source_bill_id, discount, created_by, prev_total, balance, client_request_id) VALUES (13, '00011', '2026-05-04 17:28:34', '140.00', 'CASH', 'PAID', '0.00', '0.00', NULL, '0.00', 'counter', '0.00', '0.00', NULL) ON CONFLICT DO NOTHING;
INSERT INTO bills (id, invoice_no, bill_date, total_amount, payment_mode, status, tsc_percent, tsc_amount, source_bill_id, discount, created_by, prev_total, balance, client_request_id) VALUES (23, '00012', '2026-05-25 14:03:06', '420.00', 'CASH', 'PAID', '0.00', '0.00', NULL, '0.00', 'counter1', '0.00', '0.00', NULL) ON CONFLICT DO NOTHING;

-- Data for table: bill_sequences (1 rows)
INSERT INTO bill_sequences (seq_date, last_value, updated_at) VALUES ('2000-01-01', 12, '2026-05-25 14:03:05') ON CONFLICT DO NOTHING;

-- Data for table: bill_items (17 rows)
INSERT INTO bill_items (id, bill_id, product_id, product_name, qty, rate, amount, bizz_percent, bizz_amount, product_code) VALUES (1, 1, NULL, 'SANDAL CREAM', 1, '140.00', '140.00', '12.00', '16.80', NULL) ON CONFLICT DO NOTHING;
INSERT INTO bill_items (id, bill_id, product_id, product_name, qty, rate, amount, bizz_percent, bizz_amount, product_code) VALUES (2, 2, NULL, 'SANDAL CREAM', 1, '140.00', '140.00', '12.00', '16.80', NULL) ON CONFLICT DO NOTHING;
INSERT INTO bill_items (id, bill_id, product_id, product_name, qty, rate, amount, bizz_percent, bizz_amount, product_code) VALUES (3, 3, NULL, 'SANDAL CREAM', 1, '140.00', '140.00', '12.00', '16.80', NULL) ON CONFLICT DO NOTHING;
INSERT INTO bill_items (id, bill_id, product_id, product_name, qty, rate, amount, bizz_percent, bizz_amount, product_code) VALUES (4, 4, NULL, 'SANDAL CREAM', 1, '140.00', '140.00', '12.00', '16.80', NULL) ON CONFLICT DO NOTHING;
INSERT INTO bill_items (id, bill_id, product_id, product_name, qty, rate, amount, bizz_percent, bizz_amount, product_code) VALUES (5, 4, NULL, 'CUCUMBER PACK', 1, '140.00', '140.00', '12.00', '16.80', NULL) ON CONFLICT DO NOTHING;
INSERT INTO bill_items (id, bill_id, product_id, product_name, qty, rate, amount, bizz_percent, bizz_amount, product_code) VALUES (6, 5, NULL, 'ROSE WATER-200 ML', 2, '70.00', '140.00', '0.00', '0.00', '1400') ON CONFLICT DO NOTHING;
INSERT INTO bill_items (id, bill_id, product_id, product_name, qty, rate, amount, bizz_percent, bizz_amount, product_code) VALUES (7, 6, NULL, 'SANDAL GEL', 3, '140.00', '420.00', '0.00', '0.00', '1445') ON CONFLICT DO NOTHING;
INSERT INTO bill_items (id, bill_id, product_id, product_name, qty, rate, amount, bizz_percent, bizz_amount, product_code) VALUES (8, 7, NULL, 'SANDAL CREAM', 1, '140.00', '140.00', '12.00', '16.80', NULL) ON CONFLICT DO NOTHING;
INSERT INTO bill_items (id, bill_id, product_id, product_name, qty, rate, amount, bizz_percent, bizz_amount, product_code) VALUES (9, 8, NULL, 'SANDAL CREAM', 1, '140.00', '140.00', '12.00', '16.80', NULL) ON CONFLICT DO NOTHING;
INSERT INTO bill_items (id, bill_id, product_id, product_name, qty, rate, amount, bizz_percent, bizz_amount, product_code) VALUES (10, 9, NULL, 'SANDAL CREAM', 1, '140.00', '140.00', '12.00', '16.80', NULL) ON CONFLICT DO NOTHING;
INSERT INTO bill_items (id, bill_id, product_id, product_name, qty, rate, amount, bizz_percent, bizz_amount, product_code) VALUES (11, 10, NULL, 'test gram coco', 250, '1.00', '250.00', '0.00', '0.00', NULL) ON CONFLICT DO NOTHING;
INSERT INTO bill_items (id, bill_id, product_id, product_name, qty, rate, amount, bizz_percent, bizz_amount, product_code) VALUES (12, 11, NULL, 'SANDAL CREAM', 1, '140.00', '140.00', '12.00', '16.80', NULL) ON CONFLICT DO NOTHING;
INSERT INTO bill_items (id, bill_id, product_id, product_name, qty, rate, amount, bizz_percent, bizz_amount, product_code) VALUES (13, 11, NULL, 'ALOVERA PACK', 1, '140.00', '140.00', '12.00', '16.80', NULL) ON CONFLICT DO NOTHING;
INSERT INTO bill_items (id, bill_id, product_id, product_name, qty, rate, amount, bizz_percent, bizz_amount, product_code) VALUES (14, 12, NULL, 'SANDAL CREAM', 1, '140.00', '140.00', '12.00', '16.80', NULL) ON CONFLICT DO NOTHING;
INSERT INTO bill_items (id, bill_id, product_id, product_name, qty, rate, amount, bizz_percent, bizz_amount, product_code) VALUES (15, 13, NULL, 'SANDAL CREAM', 1, '140.00', '140.00', '12.00', '16.80', NULL) ON CONFLICT DO NOTHING;
INSERT INTO bill_items (id, bill_id, product_id, product_name, qty, rate, amount, bizz_percent, bizz_amount, product_code) VALUES (28, 23, NULL, 'SANDAL CREAM', 2, '140.00', '280.00', '12.00', '33.60', NULL) ON CONFLICT DO NOTHING;
INSERT INTO bill_items (id, bill_id, product_id, product_name, qty, rate, amount, bizz_percent, bizz_amount, product_code) VALUES (29, 23, NULL, 'ALOVERA PACK', 1, '140.00', '140.00', '12.00', '16.80', NULL) ON CONFLICT DO NOTHING;

-- Data for table: stock_movements (4 rows)
INSERT INTO stock_movements (id, product_id, bill_id, movement_type, qty_change, stock_before, stock_after, created_by, created_at) VALUES (1, 275, NULL, 'ADJUSTMENT', '1000.00', '100.00', '1100.00', 'admin', '2026-04-29 12:00:44') ON CONFLICT DO NOTHING;
INSERT INTO stock_movements (id, product_id, bill_id, movement_type, qty_change, stock_before, stock_after, created_by, created_at) VALUES (2, 45, NULL, 'ADJUSTMENT', '1.00', '69.00', '70.00', 'admin', '2026-04-30 22:45:42') ON CONFLICT DO NOTHING;
INSERT INTO stock_movements (id, product_id, bill_id, movement_type, qty_change, stock_before, stock_after, created_by, created_at) VALUES (3, 275, NULL, 'ADJUSTMENT', '250.00', '850.00', '1100.00', 'admin', '2026-04-30 22:46:07') ON CONFLICT DO NOTHING;
INSERT INTO stock_movements (id, product_id, bill_id, movement_type, qty_change, stock_before, stock_after, created_by, created_at) VALUES (4, 39, NULL, 'ADJUSTMENT', '-98.00', '100.00', '2.00', 'admin', '2026-05-25 23:49:57') ON CONFLICT DO NOTHING;

-- Table returns_log is currently empty.

-- Data for table: expenses (18 rows)
INSERT INTO expenses (id, category, description, amount, expense_date, expense_group) VALUES (1, 'Rent', 'Monthly Shop Rent', '5000.00', '2026-04-25 00:00:00', 'OFFICE') ON CONFLICT DO NOTHING;
INSERT INTO expenses (id, category, description, amount, expense_date, expense_group) VALUES (2, 'Electricity', 'Power Bill', '1200.00', '2026-04-25 00:00:00', 'OFFICE') ON CONFLICT DO NOTHING;
INSERT INTO expenses (id, category, description, amount, expense_date, expense_group) VALUES (3, 'Supplies', 'Tea & Snacks', '350.00', '2026-04-25 00:00:00', 'OFFICE') ON CONFLICT DO NOTHING;
INSERT INTO expenses (id, category, description, amount, expense_date, expense_group) VALUES (4, 'BETA', NULL, '100.00', '2026-05-24 00:00:00', 'OFFICE') ON CONFLICT DO NOTHING;
INSERT INTO expenses (id, category, description, amount, expense_date, expense_group) VALUES (5, 'TSC', NULL, '50.00', '2026-05-24 00:00:00', 'OFFICE') ON CONFLICT DO NOTHING;
INSERT INTO expenses (id, category, description, amount, expense_date, expense_group) VALUES (6, 'OFFICE', NULL, '250.00', '2026-05-24 00:00:00', 'OFFICE') ON CONFLICT DO NOTHING;
INSERT INTO expenses (id, category, description, amount, expense_date, expense_group) VALUES (7, 'FLOWER', NULL, '30.00', '2026-05-24 00:00:00', 'SHOP') ON CONFLICT DO NOTHING;
INSERT INTO expenses (id, category, description, amount, expense_date, expense_group) VALUES (8, 'PACKING', NULL, '70.00', '2026-05-24 00:00:00', 'SHOP') ON CONFLICT DO NOTHING;
INSERT INTO expenses (id, category, description, amount, expense_date, expense_group) VALUES (9, 'BETA', NULL, '100.00', '2026-05-24 00:00:00', 'OFFICE') ON CONFLICT DO NOTHING;
INSERT INTO expenses (id, category, description, amount, expense_date, expense_group) VALUES (10, 'TSC', NULL, '50.00', '2026-05-24 00:00:00', 'OFFICE') ON CONFLICT DO NOTHING;
INSERT INTO expenses (id, category, description, amount, expense_date, expense_group) VALUES (11, 'OFFICE', NULL, '250.00', '2026-05-24 00:00:00', 'OFFICE') ON CONFLICT DO NOTHING;
INSERT INTO expenses (id, category, description, amount, expense_date, expense_group) VALUES (12, 'FLOWER', NULL, '30.00', '2026-05-24 00:00:00', 'SHOP') ON CONFLICT DO NOTHING;
INSERT INTO expenses (id, category, description, amount, expense_date, expense_group) VALUES (13, 'PACKING', NULL, '70.00', '2026-05-24 00:00:00', 'SHOP') ON CONFLICT DO NOTHING;
INSERT INTO expenses (id, category, description, amount, expense_date, expense_group) VALUES (14, 'BETA', NULL, '100.00', '2026-05-24 00:00:00', 'OFFICE') ON CONFLICT DO NOTHING;
INSERT INTO expenses (id, category, description, amount, expense_date, expense_group) VALUES (15, 'TSC', NULL, '50.00', '2026-05-24 00:00:00', 'OFFICE') ON CONFLICT DO NOTHING;
INSERT INTO expenses (id, category, description, amount, expense_date, expense_group) VALUES (16, 'OFFICE', NULL, '248.00', '2026-05-24 00:00:00', 'OFFICE') ON CONFLICT DO NOTHING;
INSERT INTO expenses (id, category, description, amount, expense_date, expense_group) VALUES (17, 'FLOWER', NULL, '30.00', '2026-05-24 00:00:00', 'SHOP') ON CONFLICT DO NOTHING;
INSERT INTO expenses (id, category, description, amount, expense_date, expense_group) VALUES (18, 'PACKING', NULL, '70.00', '2026-05-24 00:00:00', 'SHOP') ON CONFLICT DO NOTHING;

-- Data for table: audit_logs (14 rows)
INSERT INTO audit_logs (id, user_id, action, table_name, record_id, old_value, new_value, action_time) VALUES (1, 'admin', 'SYSTEM_RESET', 'database', 0, 'ALL_DATA', 'Financial Year Reset Executed', '2026-04-24 15:34:32') ON CONFLICT DO NOTHING;
INSERT INTO audit_logs (id, user_id, action, table_name, record_id, old_value, new_value, action_time) VALUES (2, 'counter1', 'CREATE_BILL', 'bills', 1, 'None', 'Invoice: 00001, Total: 140.0', '2026-04-24 15:35:41') ON CONFLICT DO NOTHING;
INSERT INTO audit_logs (id, user_id, action, table_name, record_id, old_value, new_value, action_time) VALUES (3, 'counter1', 'CREATE_BILL', 'bills', 2, 'None', 'Invoice: 00002, Total: 140.0', '2026-04-24 16:42:00') ON CONFLICT DO NOTHING;
INSERT INTO audit_logs (id, user_id, action, table_name, record_id, old_value, new_value, action_time) VALUES (4, 'counter1', 'CREATE_BILL', 'bills', 3, 'None', 'Invoice: 00003, Total: 140.0', '2026-04-24 16:44:13') ON CONFLICT DO NOTHING;
INSERT INTO audit_logs (id, user_id, action, table_name, record_id, old_value, new_value, action_time) VALUES (5, 'counter1', 'CREATE_BILL', 'bills', 4, 'None', 'Invoice: 00004, Total: 280.0', '2026-04-25 00:05:15') ON CONFLICT DO NOTHING;
INSERT INTO audit_logs (id, user_id, action, table_name, record_id, old_value, new_value, action_time) VALUES (6, 'counter1', 'CREATE_BILL', 'bills', 7, 'None', 'Invoice: 00005, Total: 140.0', '2026-04-27 15:18:17') ON CONFLICT DO NOTHING;
INSERT INTO audit_logs (id, user_id, action, table_name, record_id, old_value, new_value, action_time) VALUES (7, 'counter1', 'CREATE_BILL', 'bills', 8, 'None', 'Invoice: 00006, Total: 140.0', '2026-04-27 15:18:35') ON CONFLICT DO NOTHING;
INSERT INTO audit_logs (id, user_id, action, table_name, record_id, old_value, new_value, action_time) VALUES (8, 'admin', 'ADD_PRODUCT', 'products', 275, 'None', 'test gram coco', '2026-04-29 11:50:45') ON CONFLICT DO NOTHING;
INSERT INTO audit_logs (id, user_id, action, table_name, record_id, old_value, new_value, action_time) VALUES (9, 'counter1', 'CREATE_BILL', 'bills', 9, 'None', 'Invoice: 00007, Total: 140.0', '2026-04-29 12:50:38') ON CONFLICT DO NOTHING;
INSERT INTO audit_logs (id, user_id, action, table_name, record_id, old_value, new_value, action_time) VALUES (10, 'counter1', 'CREATE_BILL', 'bills', 10, 'None', 'Invoice: 00008, Total: 250.0', '2026-04-29 12:51:36') ON CONFLICT DO NOTHING;
INSERT INTO audit_logs (id, user_id, action, table_name, record_id, old_value, new_value, action_time) VALUES (11, 'counter1', 'CREATE_BILL', 'bills', 11, 'None', 'Invoice: 00009, Total: 280.0', '2026-05-04 17:19:54') ON CONFLICT DO NOTHING;
INSERT INTO audit_logs (id, user_id, action, table_name, record_id, old_value, new_value, action_time) VALUES (12, 'counter1', 'CREATE_BILL', 'bills', 12, 'None', 'Invoice: 00010, Total: 140.0', '2026-05-04 17:23:25') ON CONFLICT DO NOTHING;
INSERT INTO audit_logs (id, user_id, action, table_name, record_id, old_value, new_value, action_time) VALUES (13, 'counter', 'CREATE_BILL', 'bills', 13, 'None', 'Invoice: 00011, Total: 140.0', '2026-05-04 17:28:33') ON CONFLICT DO NOTHING;
INSERT INTO audit_logs (id, user_id, action, table_name, record_id, old_value, new_value, action_time) VALUES (14, 'counter1', 'CREATE_BILL', 'bills', 23, 'None', 'Invoice: 00012, Total: 420.0', '2026-05-25 14:03:05') ON CONFLICT DO NOTHING;

-- Data for table: cash_balance (1 rows)
INSERT INTO cash_balance (id, balance_date, opening_balance, actual_closing, closing_balance, difference, status, inflow) VALUES (1, '2026-05-24', '2500.00', '4300.00', '1002.00', '3298.00', 'OPEN', '0.00') ON CONFLICT DO NOTHING;

-- Data for table: denominations (3 rows)
INSERT INTO denominations (id, balance_id, note_value, count) VALUES (7, 1, 500, 7) ON CONFLICT DO NOTHING;
INSERT INTO denominations (id, balance_id, note_value, count) VALUES (8, 1, 200, 3) ON CONFLICT DO NOTHING;
INSERT INTO denominations (id, balance_id, note_value, count) VALUES (9, 1, 100, 2) ON CONFLICT DO NOTHING;


SET session_replication_role = 'origin';
