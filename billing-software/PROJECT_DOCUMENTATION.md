# Maple Super Market - Billing Software Documentation

## 1. Project Overview
**Maple Super Market Billing Software** (also known as Maple Pro) is a comprehensive, web-based retail management system designed for efficient point-of-sale operations, inventory tracking, and deep financial analytics. The system follows a dual-role architecture (Admin and Sales) to ensure secure and optimized workflows for both management and counter staff.

### Core Philosophy
The software is built with a focus on speed, visual excellence, and detailed reporting. It handles complex business logic like **Bizz Points** (loyalty/charges) and **TSC** (Technical Service Charges) automatically during the billing process.

---

## 2. Technology Stack
The application leverages modern web technologies for a seamless and responsive experience:

*   **Backend:** Python 3.x with **Flask** Framework.
*   **Database:** **MySQL** for robust data persistence and structured querying.
*   **Frontend:**
    *   **Structure:** Semantic HTML5.
    *   **Styling:** Custom Vanilla CSS with a focus on "Maple Pro" branding, interactive hover effects, and premium aesthetics.
    *   **Logic:** Vanilla JavaScript (ES6+) using the Fetch API for real-time data updates without page reloads.
*   **Printing:** Integrated support for thermal printers (specifically **Epson TM-T82X**) via browser print and specialized formatting.
*   **Animations:** Dynamic CSS and JS animations, including a signature "Falling Maple Leaf" effect on the login screen.

---

## 3. Key Features & Modules

### 3.1 Advanced Point of Sale (POS)
*   **Fast Checkout:** Optimized for speed with keyboard shortcuts and auto-focusing fields.
*   **Product Search:** Supports QR code/Barcode scanning and manual name search.
*   **Real-time Calculations:** Automatic calculation of Net Total, Bizz Points, and TSC.
*   **Payment Versatility:** Supports Cash, UPI, Card, and Credit sales.
*   **Instant Printing:** Automatic bill printing upon sale completion with customizable templates.

### 3.2 Inventory Management
*   **Product Master:** Comprehensive control over product details, pricing, units, and categories.
*   **Category Management:** Logical grouping of products for easier reporting.
*   **Stock Tracking:** Real-time stock level monitoring with unit-wise management.
*   **Stock Transfer:** Ability to record movement of stock between different locations (Godown vs. Main Shop).

### 3.3 Returns & Voids
*   **Bill Cancellation:** Secure workflow to void incorrect bills.
*   **Partial Returns:** Process returns for specific items within a bill.
*   **Restocking:** Option to automatically add returned items back into inventory.
*   **Returns Log:** Detailed audit trail for all return transactions.

### 3.4 Financial & Expense Management
*   **Expense Tracking:** Categorized daily expenses (Flower, Packing, Misc, etc.).
*   **Cash Balance:** A dedicated module for daily cash closure, including denomination-wise counting and difference reporting.
*   **Closure Reports:** End-of-day summaries combining sales, expenses, and expected vs. actual cash.

---

## 4. Comprehensive Reporting System
The software offers 20+ types of reports to give an in-depth view of the business:

| Report Type | Description |
| :--- | :--- |
| **Billwise Sales** | Detailed list of every bill issued with payment modes. |
| **Daily Sales Report** | A spreadsheet-style daily summary with category-wise breakdowns. |
| **Payment Reports** | Analytical view of Cash vs. UPI vs. Card vs. Credit sales with KPI cards. |
| **Category Reports** | Revenue analysis grouped by product categories (Oils, Spices, Tea, etc.). |
| **Product Reports** | Item-wise sales performance tracking. |
| **Bizz Reports** | Analysis of loyalty points and business charges generated. |
| **TSC Reports** | Tracking of Technical Service Charges collected. |
| **Stock Reports** | Current stock status and value inventory. |
| **Cancelled Bills** | Audit trail of all voided transactions with reasons. |
| **Expense Reports** | Detailed breakdown of all operational costs. |
| **Final Report (Admin)** | Master summary for management covering all KPIs. |
| **Cash Balance Report** | History of daily cash closures and discrepancies. |

---

## 5. Recent Enhancements (What We Did)
During the development phase, several critical improvements were implemented:

1.  **Backend Migration:** Successfully migrated the entire backend architecture from FastAPI to **Flask** for better compatibility and flexibility.
2.  **UI/UX Overhaul:** 
    *   Implemented a premium login page with falling maple leaf animations.
    *   Standardized report layouts with consistent headers and date displays.
    *   Refined the POS interface to eliminate scrolling and improve scanner focus.
3.  **Customer Engagement:** Added a **Customer Data** section with **Bulk SMS Broadcast** capabilities for marketing offers.
4.  **Hardware Integration:** Fully integrated POS printing for **Epson TM-T82X** thermal printers.
5.  **Data Integrity:** Implemented rigorous database health checks and schema migrations to handle "0-row" edge cases and new columns (Bizz/TSC).
6.  **Tamil Support:** Optimized bill templates to support Tamil text output while keeping the software interface in English.

---

## 6. Security and Roles
*   **Admin Role:** Full access to all masters, stock management, deep analytics, and delete/void functionalities.
*   **Sales Role:** Lightweight interface focused on Billing, Returns, and Daily Expense entry.
*   **Session Management:** Secure logout and role-based route protection.

---

**Maple Super Market Billing Software - 2026**
*Designed for Excellence, Built for Growth.*
