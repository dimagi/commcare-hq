from decimal import Decimal

UNDERSTOCK_THRESHOLD = 0.5  # months
OVERSTOCK_THRESHOLD = 2.  # months


def months_of_stock_remaining(stock, daily_consumption):
    if daily_consumption:
        return stock / Decimal((daily_consumption * 30))
    else:
        return None


def stock_category(stock, daily_consumption):
    if stock is None:
        return 'nodata'
    elif stock == 0:
        return 'stockout'
    elif daily_consumption is None:
        return 'nodata'
    elif daily_consumption == 0:
        return 'overstock'

    months_left = months_of_stock_remaining(stock, daily_consumption)

    if months_left is None:
        return 'nodata'
    elif months_left < UNDERSTOCK_THRESHOLD:
        return 'understock'
    elif months_left > OVERSTOCK_THRESHOLD:
        return 'overstock'
    else:
        return 'adequate'
