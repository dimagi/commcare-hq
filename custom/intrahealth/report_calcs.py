import fluff
import re
import logging
from corehq.apps.locations.models import Location
from custom.intrahealth import get_location_by_type, PRODUCT_MAPPING


def form_date(form):
    return form.received_on

def real_date(form):
    return form.form['real_date']

def numeric_value(val):
    number = 0
    try:
        number = int(val)
    except ValueError:
        logging.info('Bad value type: %s' %(val))
    return number

class PPSRegistered(fluff.Calculator):
    @fluff.date_emitter
    def total_for_region(self, form):
        loc = get_location_by_type(form=form, type=u'r\xe9gion')
        count = Location.filter_by_type_count(form.domain, 'PPS', loc)
        yield {
            'date': form_date(form),
            'value': count
        }

    @fluff.date_emitter
    def total_for_district(self, form):
        loc = get_location_by_type(form=form, type=u'district')
        count = Location.filter_by_type_count(form.domain, 'PPS', loc)
        yield {
            'date': form_date(form),
            'value': count
        }


class PPSPlaned(fluff.Calculator):
    @fluff.date_emitter
    def total(self, form):
        yield {
            'date': form_date(form),
            'value': 0
        }

class Commandes(fluff.Calculator):
    @fluff.date_emitter
    def total(self, form):
        if 'num_products' in form.form and form.form['num_products'] > 1:
            products = form.form['products']
            for product in products:
                if 'productName' in product and 'receivedMonthInner' in product and product['receivedMonthInner']:
                    yield {
                        'date': product['receivedMonthInner'],
                        'value': product['amountOrdered'],
                        'group_by': [product['productName']]
                    }
        elif 'productName' in form.form['products'] and 'receivedMonthInner' in form.form['products']\
            and form.form['products']['receivedMonthInner']:
            yield {
                'date': form.form['products']['receivedMonthInner'],
                'value': form.form['products']['amountOrdered'],
                'group_by': [form.form['products']['productName']]
            }

class Recus(fluff.Calculator):
    @fluff.date_emitter
    def total(self, form):
        if 'num_products' in form.form and form.form['num_products'] > 1:
            products = form.form['products']
            for product in products:
                if 'productName' in product and 'receivedMonthInner' in product and product['receivedMonthInner']:
                    yield {
                        'date': product['receivedMonthInner'],
                        'value': product['amountReceived'],
                        'group_by': [product['productName']]
                    }
        elif 'productName' in form.form['products'] and 'receivedMonthInner' in form.form['products']\
            and form.form['products']['receivedMonthInner']:
            yield {
                'date': form.form['products']['receivedMonthInner'],
                'value': form.form['products']['amountOrdered'],
                'group_by': [form.form['products']['productName']]
            }

class PPSConsumption(fluff.Calculator):

    def __init__(self, field='actual_consumption'):
        super(PPSConsumption, self).__init__()
        self.field = field

    @fluff.date_emitter
    def total(self, form):
        if 'num_products' in form.form and form.form['num_products'] > 1:
            for product in form.form['products']:
                if 'real_date' in form.form and form.form['real_date'] and 'product_name' in product:
                    yield {
                        'date': real_date(form),
                        'value': product[self.field],
                        'group_by': [product['product_name']]
                    }
        elif 'real_date' in form.form and form.form['real_date'] and 'product_name' in form.form['products']:
            yield {
                'date': real_date(form),
                'value': form.form['products'][self.field],
                'group_by': [form.form['products']['product_name']]
            }



class RupturesDeStocks(fluff.Calculator):

    def __init__(self, field='pps_stocked_out'):
        super(RupturesDeStocks, self).__init__()
        self.field = field

    @fluff.date_emitter
    def total(self, form):
        for k, v in form.form.iteritems():
            if re.match("^rupture.*hv$", k):
                if 'date_rapportage' in form.form and form.form['date_rapportage']:
                     yield {
                        'date': form.form['date_rapportage'],
                        'value': v,
                        'group_by': [PRODUCT_MAPPING[k[8:-3]]]
                    }


class RecapPassage(fluff.Calculator):

    @fluff.date_emitter
    def old_stock_total(self, form):
        if 'num_products' in form.form and form.form['num_products'] > 1:
            for product in form.form['products']:
                if 'real_date' in form.form and form.form['real_date'] and 'product_name' in product:
                    val = numeric_value(product['old_stock_total'])
                    yield {
                        'date': real_date(form),
                        "value": val,
                        "group_by": [product['product_name']]
                    }
        elif 'real_date' in form.form and form.form['real_date'] and 'product_name' in form.form['products']:
            yield {
                'date': real_date(form),
                'value': form.form['products']['old_stock_total'],
                'group_by': [form.form['products']['product_name']]
            }

    @fluff.date_emitter
    def total_stock(self, form):
        if 'num_products' in form.form and form.form['num_products'] > 1:
            for product in form.form['products']:
                if 'real_date' in form.form and form.form['real_date'] and 'product_name' in product:
                    val = numeric_value(product['total_stock'])
                    yield {
                        'date': real_date(form),
                        "value": val,
                        "group_by": [product['product_name']]
                    }
        elif 'real_date' in form.form and form.form['real_date'] and 'product_name' in form.form['products']:
            yield {
                'date': real_date(form),
                'value': form.form['products']['total_stock'],
                'group_by': [form.form['products']['product_name']]
            }

    @fluff.date_emitter
    def livraison(self, form):
        if 'num_products' in form.form and form.form['num_products'] > 1:
            for product in form.form['products']:
                if 'real_date' in form.form and form.form['real_date'] and 'product_name' in product:
                    val = numeric_value(product['top_up']['transfer']['entry']['value']['@quantity'])
                    yield {
                        'date': real_date(form),
                        "value": val,
                        "group_by": [product['product_name']]
                }
        elif 'real_date' in form.form and form.form['real_date'] and 'product_name' in form.form['products']:
            val = numeric_value(form.form['products']['top_up']['transfer']['entry']['value']['@quantity'])
            yield {
                'date': real_date(form),
                'value': val,
                'group_by': [form.form['products']['product_name']]
            }

    @fluff.date_emitter
    def display_total_stock(self, form):
        if 'num_products' in form.form and form.form['num_products'] > 1:
            for product in form.form['products']:
                if 'real_date' in form.form and form.form['real_date'] and 'product_name' in product:
                    val = numeric_value(product['display_total_stock'])
                    yield {
                        'date': real_date(form),
                        "value": val,
                        "group_by": [product['product_name']]
                    }
        elif 'real_date' in form.form and form.form['real_date'] and 'product_name' in form.form['products']:
            yield {
                'date': real_date(form),
                'value': form.form['products']['display_total_stock'],
                'group_by': [form.form['products']['product_name']]
            }

    @fluff.date_emitter
    def old_stock_pps(self, form):
        if 'num_products' in form.form and form.form['num_products'] > 1:
            for product in form.form['products']:
                if 'real_date' in form.form and form.form['real_date'] and 'product_name' in product:
                    val = numeric_value(product['old_stock_pps'])
                    yield {
                        'date': real_date(form),
                        "value": val,
                        "group_by": [product['product_name']]
                    }
        elif 'real_date' in form.form and form.form['real_date'] and 'product_name' in form.form['products']:
            yield {
                'date': real_date(form),
                'value': form.form['products']['old_stock_pps'],
                'group_by': [form.form['products']['product_name']]
            }

    @fluff.date_emitter
    def outside_receipts_amount(self, form):
        if 'num_products' in form.form and form.form['num_products'] > 1:
            for product in form.form['products']:
                if 'real_date' in form.form and form.form['real_date'] and 'product_name' in product:
                    val = numeric_value(product['outside_receipts_amt'])
                    yield {
                        "date": real_date(form),
                        "value": val,
                        "group_by": [product['product_name']]
                    }
        elif 'real_date' in form.form and form.form['real_date'] and 'product_name' in form.form['products']:
            yield {
                'date': real_date(form),
                'value': form.form['products']['outside_receipts_amt'],
                'group_by': [form.form['products']['product_name']]
            }

    @fluff.date_emitter
    def actual_consumption(self, form):
        if 'num_products' in form.form and form.form['num_products'] > 1:
            for product in form.form['products']:
                if 'real_date' in form.form and form.form['real_date'] and 'product_name' in product:
                    val = numeric_value(product['actual_consumption'])
                    yield {
                        'date': real_date(form),
                        "value": val,
                        "group_by": [product['product_name']]
                    }
        elif 'real_date' in form.form and form.form['real_date'] and 'product_name' in form.form['products']:
            yield {
                'date': real_date(form),
                'value': form.form['products']['actual_consumption'],
                'group_by': [form.form['products']['product_name']]
            }

    @fluff.date_emitter
    def billed_consumption(self, form):
        if 'num_products' in form.form and form.form['num_products'] > 1:
            for product in form.form['products']:
                if 'real_date' in form.form and form.form['real_date'] and 'product_name' in product:
                    val = numeric_value(product['billed_consumption'])
                    yield {
                        'date': real_date(form),
                        "value": val,
                        "group_by": [product['product_name']]
                    }
        elif 'real_date' in form.form and form.form['real_date'] and 'product_name' in form.form['products']:
            yield {
                'date': real_date(form),
                'value': form.form['products']['billed_consumption'],
                'group_by': [form.form['products']['product_name']]
            }

    @fluff.date_emitter
    def pps_restant(self, form):
        if 'num_products' in form.form and form.form['num_products'] > 1:
            for product in form.form['products']:
                if 'real_date' in form.form and form.form['real_date'] and 'product_name' in product:
                    val = numeric_value(product['pps_stock'])
                    yield {
                        'date': real_date(form),
                        "value": val if val >= 0 else 0,
                        "group_by": [product['product_name']]
                    }
        elif 'real_date' in form.form and form.form['real_date'] and 'product_name' in form.form['products']:
            yield {
                'date': real_date(form),
                'value': form.form['products']['pps_stock'],
                'group_by': [form.form['products']['product_name']]
            }

    @fluff.date_emitter
    def loss_amt(self, form):
        if 'num_products' in form.form and form.form['num_products'] > 1:
            for product in form.form['products']:
                if 'real_date' in form.form and form.form['real_date'] and 'product_name' in product\
                        and product['loss_amt']:
                    yield {
                        'date': real_date(form),
                        "value": int(product['loss_amt']),
                        "group_by": [product['product_name']]
                    }
        elif 'real_date' in form.form and form.form['real_date'] and 'product_name' in form.form['products']:
            yield {
                'date': real_date(form),
                'value': form.form['products']['loss_amt'],
                'group_by': [form.form['products']['product_name']]
            }

class DureeMoyenneLivraison(fluff.Calculator):

    @fluff.date_emitter
    def total(self, form):
        value = form.form['duree_moyenne_livraison'] if form.form['duree_moyenne_livraison'] else 0
        yield {
            'date': form.form['mois_visite'],
            'value': value
        }
