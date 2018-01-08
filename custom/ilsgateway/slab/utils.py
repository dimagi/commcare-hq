from __future__ import absolute_import
from collections import OrderedDict
from datetime import timedelta, date

from decimal import Decimal

from casexml.apps.stock.models import StockTransaction
from corehq.apps.commtrack.models import StockState
import six


def get_current_state(sql_location):
    ten_days_ago = date.today() - timedelta(days=10)
    consumptions_by_product = {
        stock_state.sql_product.code: stock_state.get_monthly_consumption()
        for stock_state in StockState.objects.filter(
            case_id=sql_location.supply_point_id
        ).select_related('sql_product').order_by('sql_product__code')
    }

    stock_transactions = StockTransaction.objects.filter(
        case_id=sql_location.supply_point_id, report__date__gte=ten_days_ago, type__in=['stockonhand', 'stockout']
    ).select_related('sql_product').distinct('sql_product__code')\
        .order_by('sql_product__code', '-report__date')

    current_state = OrderedDict()
    for stock_transaction in stock_transactions:
        code = stock_transaction.sql_product.code
        current_state[code] = (stock_transaction.stock_on_hand, None)
        consumption = consumptions_by_product.get(code)
        if consumption:
            current_state[code] = (stock_transaction.stock_on_hand, consumption)
    return current_state


def overstocked_products(sql_location):
    if sql_location.location_type.administrative:
        return {}

    overstocked_products_list = []

    for product_code, (stock_on_hand, monthly_consumption) in six.iteritems(get_current_state(sql_location)):
        if not monthly_consumption:
            continue
        remaining = stock_on_hand / Decimal(monthly_consumption)

        if remaining > 6:
            overstocked_products_list.append(
                (product_code, int(stock_on_hand), int(6 * monthly_consumption))
            )

    return overstocked_products_list


def stockedout_products(sql_location):
    if sql_location.location_type.administrative:
        return {}

    stocked_out_list = []
    for product_code, (stock_on_hand, monthly_consumption) in six.iteritems(get_current_state(sql_location)):
        if stock_on_hand == 0:
            stocked_out_list.append(product_code)

        if not monthly_consumption:
            continue

        remaining = stock_on_hand / Decimal(monthly_consumption)
        if remaining < 0.35:
            stocked_out_list.append(product_code)

    return stocked_out_list
