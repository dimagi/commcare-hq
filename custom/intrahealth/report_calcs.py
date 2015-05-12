from corehq.apps.products.models import SQLProduct
import fluff
import re
import logging
from corehq.apps.locations.models import Location
from custom.intrahealth import get_location_by_type, PRODUCT_MAPPING, get_domain, PRODUCT_NAMES, get_district_name


def form_date(form):
    return form.received_on


def real_date(form):
    return form.form['real_date']


def numeric_value(val):
    number = 0
    try:
        number = int(val)
    except ValueError:
        logging.info('Bad value type: %s' % val)
    return number


def get_product_code(product_name, domain):
    try:
        return SQLProduct.objects.get(name=product_name, domain=domain).code
    except SQLProduct.DoesNotExist:
        for k, v in PRODUCT_NAMES.iteritems():
            if product_name.lower() in v:
                return SQLProduct.objects.get(name__iexact=k,
                                              domain=domain).code


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
                        'group_by': [product['productName'],
                                     get_product_code(product['productName'], get_domain(form))]
                    }
        elif 'productName' in form.form['products'] and 'receivedMonthInner' in form.form['products']\
             and form.form['products']['receivedMonthInner']:
            yield {
                'date': form.form['products']['receivedMonthInner'],
                'value': form.form['products']['amountOrdered'],
                'group_by': [form.form['products']['productName'],
                             get_product_code(form.form['products']['productName'], get_domain(form))]
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
                        'group_by': [product['productName'],
                                     get_product_code(product['productName'], get_domain(form))]
                    }
        elif 'productName' in form.form['products'] and \
             'receivedMonthInner' in form.form['products'] and \
             form.form['products']['receivedMonthInner']:
            yield {
                'date': form.form['products']['receivedMonthInner'],
                'value': form.form['products']['amountOrdered'],
                'group_by': [form.form['products']['productName'],
                             get_product_code(form.form['products']['productName'], get_domain(form))]
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
                        'group_by': [product['product_name'],
                                     get_product_code(product['product_name'], get_domain(form))]
                    }
        elif 'real_date' in form.form and form.form['real_date'] and 'product_name' in form.form['products']:
            yield {
                'date': real_date(form),
                'value': form.form['products'][self.field],
                'group_by': [form.form['products']['product_name'],
                             get_product_code(form.form['products']['product_name'], get_domain(form))]
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
                    product_name = PRODUCT_NAMES.get(PRODUCT_MAPPING[k[8:-3]].lower())
                    if product_name is not None:
                        try:
                            prd = SQLProduct.objects.get(name__iexact=product_name,
                                                         domain=get_domain(form))
                            yield {
                                'date': form.form['date_rapportage'],
                                'value': v,
                                'group_by': [PRODUCT_MAPPING[k[8:-3]], prd.code]
                            }
                        except SQLProduct.DoesNotExist:
                            pass


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
                        "group_by": [product['product_name'],
                                     get_product_code(product['product_name'], get_domain(form))]
                    }
        elif 'real_date' in form.form and form.form['real_date'] and 'product_name' in form.form['products']:
            yield {
                'date': real_date(form),
                'value': form.form['products']['old_stock_total'],
                'group_by': [form.form['products']['product_name'],
                             get_product_code(form.form['products']['product_name'], get_domain(form))]
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
                        'group_by': [product['product_name'],
                                     get_product_code(product['product_name'], get_domain(form))]
                    }
        elif 'real_date' in form.form and form.form['real_date'] and 'product_name' in form.form['products']:
            yield {
                'date': real_date(form),
                'value': form.form['products']['total_stock'],
                'group_by': [form.form['products']['product_name'],
                             get_product_code(form.form['products']['product_name'], get_domain(form))]
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
                        'group_by': [product['product_name'],
                                     get_product_code(product['product_name'], get_domain(form))]
                    }
        elif 'real_date' in form.form and form.form['real_date'] and 'product_name' in form.form['products']:
            val = numeric_value(form.form['products']['top_up']['transfer']['entry']['value']['@quantity'])
            yield {
                'date': real_date(form),
                'value': val,
                'group_by': [form.form['products']['product_name'],
                             get_product_code(form.form['products']['product_name'], get_domain(form))]
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
                        'group_by': [product['product_name'],
                                     get_product_code(product['product_name'], get_domain(form))]
                    }
        elif 'real_date' in form.form and form.form['real_date'] and 'product_name' in form.form['products']:
            yield {
                'date': real_date(form),
                'value': form.form['products']['display_total_stock'],
                'group_by': [form.form['products']['product_name'],
                             get_product_code(form.form['products']['product_name'], get_domain(form))]
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
                        'group_by': [product['product_name'],
                                     get_product_code(product['product_name'], get_domain(form))]
                    }
        elif 'real_date' in form.form and form.form['real_date'] and 'product_name' in form.form['products']:
            yield {
                'date': real_date(form),
                'value': form.form['products']['old_stock_pps'],
                'group_by': [form.form['products']['product_name'],
                             get_product_code(form.form['products']['product_name'], get_domain(form))]
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
                        'group_by': [product['product_name'],
                                     get_product_code(product['product_name'], get_domain(form))]
                    }
        elif 'real_date' in form.form and form.form['real_date'] and 'product_name' in form.form['products']:
            yield {
                'date': real_date(form),
                'value': form.form['products']['outside_receipts_amt'],
                'group_by': [form.form['products']['product_name'],
                             get_product_code(form.form['products']['product_name'], get_domain(form))]
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
                        'group_by': [product['product_name'],
                                     get_product_code(product['product_name'], get_domain(form))]
                    }
        elif 'real_date' in form.form and form.form['real_date'] and 'product_name' in form.form['products']:
            yield {
                'date': real_date(form),
                'value': form.form['products']['actual_consumption'],
                'group_by': [form.form['products']['product_name'],
                             get_product_code(form.form['products']['product_name'], get_domain(form))]
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
                        'group_by': [product['product_name'],
                                     get_product_code(product['product_name'], get_domain(form))]
                    }
        elif 'real_date' in form.form and form.form['real_date'] and 'product_name' in form.form['products']:
            yield {
                'date': real_date(form),
                'value': form.form['products']['billed_consumption'],
                'group_by': [form.form['products']['product_name'],
                             get_product_code(form.form['products']['product_name'], get_domain(form))]
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
                        'group_by': [product['product_name'],
                                     get_product_code(product['product_name'], get_domain(form))]
                    }
        elif 'real_date' in form.form and form.form['real_date'] and 'product_name' in form.form['products']:
            yield {
                'date': real_date(form),
                'value': form.form['products']['pps_stock'],
                'group_by': [form.form['products']['product_name'],
                             get_product_code(form.form['products']['product_name'], get_domain(form))]
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
                        'group_by': [product['product_name'],
                                     get_product_code(product['product_name'], get_domain(form))]
                    }
        elif 'real_date' in form.form and form.form['real_date'] and 'product_name' in form.form['products']:
            yield {
                'date': real_date(form),
                'value': form.form['products']['loss_amt'],
                'group_by': [form.form['products']['product_name'],
                             get_product_code(form.form['products']['product_name'], get_domain(form))]
            }

class DureeMoyenneLivraison(fluff.Calculator):

    @fluff.date_emitter
    def total(self, form):
        value = form.form['duree_moyenne_livraison'] if form.form['duree_moyenne_livraison'] else 0
        yield {
            'date': form.form['mois_visite'],
            'value': value
        }


class Recouvrement(fluff.Calculator):

    @fluff.date_emitter
    def amount_to_pay(self, form):
        if 'quantite_reale_a_payer' in form.form and 'date_du' in form.form and form.form['date_du']:
            value = form.form['quantite_reale_a_payer']

            yield {
                'date': form.form['date_du'],
                'value': value,
                'group_by': [get_district_name(form),
                             get_domain(form)]
            }

    @fluff.date_emitter
    def amount_paid(self, form):
        if 'montant_payer' in form.form and 'date_du' in form.form and form.form['date_du']:
            value = form.form['montant_paye']

            yield {
                'date': form.form['date_du'],
                'value': value,
                'group_by': [get_district_name(form),
                             get_domain(form)]
            }

    @fluff.date_emitter
    def in_30_days(self, form):
        if 'payee_trent_jour' in form.form and 'date_du' in form.form and form.form['date_du']:
            value = form.form['payee_trent_jour']

            yield {
                'date': form.form['date_du'],
                'value': value,
                'group_by': [get_district_name(form),
                             get_domain(form)]
            }

    @fluff.date_emitter
    def in_3_months(self, form):
        if 'payee_trois_mois' in form.form and 'date_du' in form.form and form.form['date_du']:
            value = form.form['payee_trois_mois']

            yield {
                'date': form.form['date_du'],
                'value': value,
                'group_by': [get_district_name(form),
                             get_domain(form)]
            }

    @fluff.date_emitter
    def in_year(self, form):
        if 'payee_un_an' in form.form and 'date_du' in form.form and form.form['date_du']:
            value = form.form['payee_un_an']

            yield {
                'date': form.form['date_du'],
                'value': value,
                'group_by': [get_district_name(form),
                             get_domain(form)]
            }
