from datetime import datetime
from corehq.apps.products.models import SQLProduct
from dimagi.utils.dates import force_to_date
import fluff
import re
import logging
from custom.intrahealth import get_location_by_type, PRODUCT_MAPPING, get_domain, PRODUCT_NAMES, get_loc_from_case


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
        k = PRODUCT_NAMES.get(product_name.lower())
        if k:
            return SQLProduct.objects.get(name__iexact=k,
                                          domain=domain).code


def _locations_per_type(domain, loc_type, location):
    return (location.sql_location.get_descendants(include_self=True)
            .filter(domain=domain, location_type__name=loc_type, is_archived=False).count())


class PPSRegistered(fluff.Calculator):
    @fluff.date_emitter
    def total_for_region(self, form):
        loc = get_location_by_type(form=form, type=u'r\xe9gion')
        count = _locations_per_type(form.domain, 'PPS', loc)
        yield {
            'date': form_date(form),
            'value': count
        }

    @fluff.date_emitter
    def total_for_district(self, form):
        loc = get_location_by_type(form=form, type=u'district')
        count = _locations_per_type(form.domain, 'PPS', loc)
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
        if 'num_products' in form.form and int(form.form['num_products']) > 1:
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
        if 'num_products' in form.form and int(form.form['num_products']) > 1:
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
        if 'num_products' in form.form and int(form.form['num_products']) > 1:
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
        if 'num_products' in form.form and int(form.form['num_products']) > 1:
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
        if 'num_products' in form.form and int(form.form['num_products']) > 1:
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
        if 'num_products' in form.form and int(form.form['num_products']) > 1:
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
        if 'num_products' in form.form and int(form.form['num_products']) > 1:
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
        if 'num_products' in form.form and int(form.form['num_products']) > 1:
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
        if 'num_products' in form.form and int(form.form['num_products']) > 1:
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
        if 'num_products' in form.form and int(form.form['num_products']) > 1:
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


def check_prop(prop, case):
    return case.get_case_property(prop) and case.get_case_property('date_du')


def get_district_name(case):
    return get_loc_from_case(case).name


def get_date_du(case):
    date = case.get_case_property('date_du')
    if type(date) is not datetime:
        return force_to_date(date)
    return date


class Recouvrement(fluff.Calculator):

    @fluff.date_emitter
    def amount_to_pay(self, case):
        if check_prop('quantite_reale_a_payer', case):
            value = case.get_case_property('quantite_reale_a_payer')

            yield {
                'date': get_date_du(case),
                'value': int(value),
                'group_by': [get_district_name(case),
                             case.get_case_property('domain')]
            }

    @fluff.date_emitter
    def amount_paid(self, case):
        if check_prop('montant_paye', case):
            value = case.get_case_property('montant_paye')

            yield {
                'date': get_date_du(case),
                'value': int(value),
                'group_by': [get_district_name(case),
                             case.get_case_property('domain')]
            }

    @fluff.date_emitter
    def in_30_days(self, case):
        if check_prop('payee_trent_jour', case):
            value = case.get_case_property('payee_trent_jour')

            yield {
                'date': get_date_du(case),
                'value': int(value),
                'group_by': [get_district_name(case),
                             case.get_case_property('domain')]
            }

    @fluff.date_emitter
    def in_3_months(self, case):
        if check_prop('payee_trois_mois', case):
            value = case.get_case_property('payee_trois_mois')

            yield {
                'date': get_date_du(case),
                'value': int(value),
                'group_by': [get_district_name(case),
                             case.get_case_property('domain')]
            }

    @fluff.date_emitter
    def in_year(self, case):
        if check_prop('payee_un_an', case):
            value = case.get_case_property('payee_un_an')

            yield {
                'date': get_date_du(case),
                'value': int(value),
                'group_by': [get_district_name(case),
                             case.get_case_property('domain')]
            }
