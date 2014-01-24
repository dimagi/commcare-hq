UNDERSTOCK_THRESHOLD = 0.5  # months
OVERSTOCK_THRESHOLD = 2.  # months


def months_of_stock_remaining(stock, consumption):
    try:
        return stock / consumption
    except (TypeError, ZeroDivisionError):
        return None


def stock_category(stock, consumption):
    if stock is None:
        return 'nodata'
    elif stock == 0:
        return 'stockout'
    elif consumption is None:
        return 'nodata'
    elif consumption == 0:
        return 'overstock'

    months_left = months_of_stock_remaining(stock, consumption)

    if months_left is None:
        return 'nodata'
    elif months_left < UNDERSTOCK_THRESHOLD:
        return 'understock'
    elif months_left > OVERSTOCK_THRESHOLD:
        return 'overstock'
    else:
        return 'adequate'
