from decimal import Decimal


def months_of_stock_remaining(stock, daily_consumption):
    if daily_consumption:
        return stock / Decimal((daily_consumption * 30))
    else:
        return None


def stock_category(stock, daily_consumption, domain):
    if stock is None:
        return 'nodata'
    elif stock == 0:
        return 'stockout'
    elif daily_consumption is None:
        return 'nodata'
    elif daily_consumption == 0:
        return 'overstock'

    months_left = months_of_stock_remaining(stock, daily_consumption)

    stock_levels = domain.commtrack_settings.stock_levels_config

    if months_left is None:
        return 'nodata'
    elif months_left < stock_levels.understock_threshold:
        return 'understock'
    elif months_left > stock_levels.overstock_threshold:
        return 'overstock'
    else:
        return 'adequate'


def state_stock_category(state):
    return stock_category(
        state.stock_on_hand,
        state.get_daily_consumption(),
        state.get_domain()
    )
