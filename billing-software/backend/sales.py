import datetime

from backend.inventory import consume_locked_stock, lock_products_for_sale


def calculate_tsc(total):
    if total >= 10000:
        return 3.0
    if total >= 7000:
        return 2.5
    if total >= 5000:
        return 2.0
    if total >= 2500:
        return 1.5
    if total >= 1000:
        return 1.0
    return 0.0


def reserve_invoice_number(cursor, bill_time):
    seq_date = bill_time.date()
    cursor.execute(
        """
        INSERT INTO bill_sequences (seq_date, last_value)
        VALUES (%s, 1)
        ON DUPLICATE KEY UPDATE last_value = LAST_INSERT_ID(last_value + 1)
        """,
        (seq_date,)
    )
    cursor.execute("SELECT LAST_INSERT_ID()")
    sequence_row = cursor.fetchone()
    sequence_value = int(
        sequence_row.get('LAST_INSERT_ID()')
        if isinstance(sequence_row, dict)
        else sequence_row[0]
    )
    if sequence_value == 0:
        cursor.execute("SELECT last_value FROM bill_sequences WHERE seq_date = %s", (seq_date,))
        fallback_row = cursor.fetchone()
        sequence_value = int(
            fallback_row.get('last_value')
            if isinstance(fallback_row, dict)
            else fallback_row[0]
        )

    return f"{bill_time.strftime('%Y%m%d')}-{sequence_value:04d}"


def create_bill(conn, payload, username, audit_logger):
    items = payload.get('items') or []
    if not items:
        raise ValueError('Add at least one item before saving the bill.')

    total = round(float(payload['total']), 2)
    discount = round(float(payload.get('discount', 0) or 0), 2)
    tsc_percent = calculate_tsc(total)
    tsc_amount = round((total * tsc_percent) / 100, 2)
    status = 'CORRECTION' if payload.get('is_correction') else 'PAID'
    payment_mode = str(payload.get('payment_mode', 'CASH')).upper()
    client_request_id = payload.get('client_request_id')
    bill_time = datetime.datetime.now()

    cursor = conn.cursor(dictionary=True)
    try:
        conn.start_transaction()

        if client_request_id:
            cursor.execute(
                "SELECT id, invoice_no FROM bills WHERE client_request_id = %s FOR UPDATE",
                (client_request_id,)
            )
            existing_bill = cursor.fetchone()
            if existing_bill:
                conn.rollback()
                return {
                    'status': 'success',
                    'bill_id': existing_bill['id'],
                    'invoice_no': existing_bill['invoice_no'],
                    'duplicate_request': True,
                }

        locked_products = lock_products_for_sale(cursor, items)
        invoice_no = reserve_invoice_number(cursor, bill_time)

        cursor.execute(
            """
            INSERT INTO bills
                (invoice_no, client_request_id, bill_date, total_amount, payment_mode,
                 tsc_percent, tsc_amount, status, source_bill_id, discount, created_by)
            VALUES
                (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                invoice_no,
                client_request_id,
                bill_time,
                total,
                payment_mode,
                tsc_percent,
                tsc_amount,
                status,
                payload.get('source_bill_id'),
                discount,
                username,
            )
        )
        bill_id = cursor.lastrowid

        for item in items:
            product_name = str(item['name']).strip()
            qty = float(item['qty'])
            rate = round(float(item['rate']), 2)
            amount = round(float(item['amount']), 2)
            bizz_percent = round(float(item.get('bizz', 0) or 0), 2)
            bizz_amount = round((amount * bizz_percent) / 100, 2)
            product = locked_products[product_name]

            cursor.execute(
                """
                INSERT INTO bill_items
                    (bill_id, product_code, product_name, qty, rate, amount, bizz_percent, bizz_amount)
                VALUES
                    (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    bill_id,
                    product['barcode'],
                    product_name,
                    qty,
                    rate,
                    amount,
                    bizz_percent,
                    bizz_amount,
                )
            )
            consume_locked_stock(cursor, product, qty, bill_id, username)

        audit_logger(
            cursor,
            'CREATE_BILL',
            'bills',
            bill_id,
            None,
            f"Invoice: {invoice_no}, Total: {total}, Items: {len(items)}",
        )
        conn.commit()
        return {
            'status': 'success',
            'bill_id': bill_id,
            'invoice_no': invoice_no,
            'duplicate_request': False,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
