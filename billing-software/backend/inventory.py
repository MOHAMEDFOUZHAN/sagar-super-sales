from collections import OrderedDict


def lock_products_for_sale(cursor, items):
    """
    Lock each unique product row in a deterministic order so concurrent
    checkouts don't deadlock each other when two cashiers sell the same items.
    """
    requested = OrderedDict()
    for item in items:
        product_name = str(item.get('name', '')).strip()
        if not product_name:
            raise ValueError('Product name is required for each bill item.')
        requested.setdefault(product_name, 0.0)
        requested[product_name] += float(item.get('qty', 0) or 0)

    locked_products = {}
    for product_name in sorted(requested.keys()):
        cursor.execute(
            """
            SELECT id, barcode, name, current_stock
            FROM products
            WHERE name = %s
            FOR UPDATE
            """,
            (product_name,)
        )
        product = cursor.fetchone()
        if not product:
            raise ValueError(f'Product not found in DB: {product_name}')

        available_stock = float(product['current_stock'] or 0)
        demanded_qty = float(requested[product_name])
        if demanded_qty <= 0:
            raise ValueError(f'Invalid quantity for {product_name}.')
        if available_stock < demanded_qty:
            raise ValueError(
                f'Insufficient stock for {product_name}. '
                f'Available: {available_stock}, Demanded: {demanded_qty}'
            )

        locked_products[product_name] = {
            'id': product['id'],
            'barcode': product['barcode'],
            'name': product['name'],
            'current_stock': available_stock,
            'demanded_qty': demanded_qty,
        }

    return locked_products


def consume_locked_stock(cursor, product, qty, bill_id, created_by):
    stock_before = float(product['current_stock'])
    stock_after = stock_before - float(qty)
    if stock_after < 0:
        raise ValueError(f'Negative stock is not allowed for {product["name"]}.')

    cursor.execute(
        "UPDATE products SET current_stock = %s WHERE id = %s",
        (stock_after, product['id'])
    )
    cursor.execute(
        """
        INSERT INTO stock_movements
            (product_id, bill_id, movement_type, qty_change, stock_before, stock_after, created_by)
        VALUES
            (%s, %s, %s, %s, %s, %s, %s)
        """,
        (
            product['id'],
            bill_id,
            'SALE',
            -float(qty),
            stock_before,
            stock_after,
            created_by,
        )
    )
    product['current_stock'] = stock_after
