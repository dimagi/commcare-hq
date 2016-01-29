from datetime import datetime
from corehq.apps.products.models import SQLProduct
from dimagi.utils.dates import force_to_date
import fluff
import re
import logging
from custom.intrahealth import get_location_by_type, PRODUCT_MAPPING, get_domain, PRODUCT_NAMES,\
    get_loc_from_case, COMMANDE_XMLNSES, OPERATEUR_XMLNSES


def get_value_from_path(dictionary, path, default_value=None):
    value = dictionary
    for key in path.split('/'):
        try:
            value = value[key]
        except Exception:
            return default_value
    return value


def form_date(form):
    return form.received_on


def real_date(form):
    return form.form['real_date']


def numeric_value(val):
    if val is None:
        return 0
    number = 0
    try:
        number = int(val)
    except ValueError:
        logging.info('Bad value type: %s' % val)
    return number


def get_product_id(product_name, domain):
    try:
        return SQLProduct.objects.get(name=product_name, domain=domain).product_id
    except SQLProduct.DoesNotExist:
        k = PRODUCT_NAMES.get(product_name.lower())
        if k:
            return SQLProduct.objects.get(name__iexact=k,
                                          domain=domain).product_id


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


class TauxCalculator(fluff.Calculator):

    def __init__(self, property_name):
        super(TauxCalculator, self).__init__()
        self.property_name = property_name

    def _process_v1_form(self, form):
        num_products = numeric_value(form.get_data('form/num_products'))
        print num_products
        if num_products > 1:
            for product in (form.xpath('form/products') or []):
                received_month_inner = product.get('receivedMonthInner')
                amount_ordered = numeric_value(product.get(self.property_name))
                product_name = product.get('productName')
                if received_month_inner and amount_ordered is not None and product_name:
                    yield {
                        'date': received_month_inner,
                        'value': amount_ordered,
                        'group_by': [product_name, get_product_id(product_name, get_domain(form))]
                    }
        else:
            received_month_inner = form.get_data('form/products/receivedMonthInner')
            amount_ordered = numeric_value(form.get_data('form/products/{}}'.format(self.property_name)))
            product_name = form.get_data('form/products/productName')
            if received_month_inner and amount_ordered and product_name:
                yield {
                    'date': received_month_inner,
                    'value': amount_ordered,
                    'group_by': [product_name, get_product_id(product_name, get_domain(form))]
                }

    def _process_v2_form(self, form):
        for product in (form.get_data('form/products/item') or []):
            received_month_inner = product.get('receivedMonthInner')
            amount_ordered = numeric_value(get_value_from_path(product, 'qlist/{}'.format(self.property_name)))
            product_name = product.get('productName')
            if received_month_inner is not None and amount_ordered is not None and product_name is not None:
                yield {
                    'date': received_month_inner,
                    'value': amount_ordered,
                    'group_by': [product_name, get_product_id(product_name, get_domain(form))]
                }

    @fluff.date_emitter
    def total(self, form):
        if form.xmlns == COMMANDE_XMLNSES[2]:
            result = self._process_v2_form(form)
        else:
            result = self._process_v1_form(form)

        return result


class PPSConsumption(fluff.Calculator):

    def __init__(self, field='actual_consumption'):
        super(PPSConsumption, self).__init__()
        self.field = field

    def _process_v1_form(self, form):
        if 'num_products' in form.form and form.form['num_products'] > 1:
            for product in form.form['products']:
                if 'real_date' in form.form and form.form['real_date'] and 'product_name' in product:
                    yield {
                        'date': real_date(form),
                        'value': product[self.field],
                        'group_by': [product['product_name'],
                                     get_product_id(product['product_name'], get_domain(form))]
                    }
        elif 'real_date' in form.form and form.form['real_date'] and 'product_name' in form.form['products']:
            yield {
                'date': real_date(form),
                'value': form.form['products'][self.field],
                'group_by': [form.get_data('form/products/product_name'),
                             get_product_id(form.get_data('form/products/product_name'), get_domain(form))]
            }

    def _process_v2_form(self, form):
        real_date = form.get_data('form/real_date')
        if not real_date:
            return

        for item in form.get_data('form/products/item', []):
            yield {
                'date': real_date,
                'value': numeric_value(get_value_from_path(item, 'is-relevant/{}'.format(self.field))),
                'group_by': [item['product_name'], get_product_id(item['product_name'], get_domain(form))]
            }

    @fluff.date_emitter
    def total(self, form):
        if form.xmlns == OPERATEUR_XMLNSES[1]:
            result = self._process_v2_form(form)
        else:
            result = self._process_v1_form(form)
        return result


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
                                'group_by': [PRODUCT_MAPPING[k[8:-3]], prd.product_id]
                            }
                        except SQLProduct.DoesNotExist:
                            pass


class RecapPassage(fluff.Calculator):

    def _process_field(self, form, getter):
        if form.xmlns == OPERATEUR_XMLNSES[1]:
            for item in form.get_data('form/products/item'):
                if 'is-relevant' is not item:
                    continue
                item = item['is-relevant']
                val = numeric_value(item)
                yield {
                    'date': real_date(form),
                    "value": val,
                    "group_by": [item['product_name'],
                                 get_product_id(item['product_name'], get_domain(form))]
                }

        if 'num_products' in form.form and int(form.form['num_products']) > 1:
            for product in form.form['products']:
                if 'real_date' in form.form and form.form['real_date'] and 'product_name' in product:
                    val = numeric_value(getter(product))
                    yield {
                        'date': real_date(form),
                        "value": val,
                        "group_by": [product['product_name'],
                                     get_product_id(product['product_name'], get_domain(form))]
                    }
        elif 'real_date' in form.form and form.form['real_date'] and 'product_name' in form.form['products']:
            yield {
                'date': real_date(form),
                'value': getter(form.form['products']),
                'group_by': [form.form['products']['product_name'],
                             get_product_id(form.form['products']['product_name'], get_domain(form))]
            }

    @fluff.date_emitter
    def old_stock_total(self, form):
        return self._process_field(form, lambda x: x['old_stock_total'])

    @fluff.date_emitter
    def total_stock(self, form):
        return self._process_field(form, lambda x: x['total_stock'])

    @fluff.date_emitter
    def livraison(self, form):
        if form.xmlns == OPERATEUR_XMLNSES[1]:
            return self._process_field(form, lambda x: x['display_stock_total'] - x['total_stock'])
        else:
            return self._process_field(form, lambda x: x['top_up']['transfer']['entry']['value']['@quantity'])

    @fluff.date_emitter
    def display_total_stock(self, form):
        return self._process_field(form, lambda x: x['display_total_stock'])

    @fluff.date_emitter
    def old_stock_pps(self, form):
        return self._process_field(form, lambda x: x['old_stock_pps'])

    @fluff.date_emitter
    def outside_receipts_amount(self, form):
        return self._process_field(form, lambda x: x['outside_receipts_amt'])

    @fluff.date_emitter
    def actual_consumption(self, form):
        return self._process_field(form, lambda x: x['actual_consumption'])

    @fluff.date_emitter
    def billed_consumption(self, form):
        return self._process_field(form, lambda x: x['billed_consumption'])

    @fluff.date_emitter
    def pps_restant(self, form):
        return self._process_field(form, lambda x: x['pps_stock'] if numeric_value(x['pps_stock']) >= 0 else 0)

    @fluff.date_emitter
    def loss_amt(self, form):
        return self._process_field(form, lambda x: x['loss_amt'])


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
