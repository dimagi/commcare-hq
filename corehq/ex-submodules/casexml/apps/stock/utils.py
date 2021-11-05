from decimal import Decimal


def months_of_stock_remaining(stock, daily_consumption):
    if daily_consumption:
        return stock / Decimal(daily_consumption * 30)
    else:
        return None


def stock_category(stock, daily_consumption, understock, overstock):
    if stock is None:
        return 'nodata'
    elif stock <= 0:
        return 'stockout'
    elif daily_consumption is None:
        return 'nodata'
    elif daily_consumption == 0:
        return 'overstock'

    months_left = months_of_stock_remaining(stock, daily_consumption)
    if months_left is None:
        return 'nodata'
    elif months_left < understock:
        return 'understock'
    elif months_left > overstock:
        return 'overstock'
    else:
        return 'adequate'
