import fluff
import re
from corehq.apps.locations.models import Location
from custom.intrahealth import get_location_by_type, PRODUCT_MAPPING


def form_date(form):
    return form.received_on

def real_date(form):
    return form.form['real_date']

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
        products = form.form['products']
        for product in products:
            if 'productName' in product and 'receivedMonthInner' in product and product['receivedMonthInner']:
                yield {
                    'date': product['receivedMonthInner'],
                    'value': product['amountOrdered'],
                    'group_by': [product['productName']]
                }

class Recus(fluff.Calculator):
    @fluff.date_emitter
    def total(self, form):
        products = form.form['products']
        for product in products:
            if 'productName' in product and 'receivedMonthInner' in product and product['receivedMonthInner']:
                yield {
                    'date': product['receivedMonthInner'],
                    'value': product['amountReceived'],
                    'group_by': [product['productName']]
                }

class PPSConsumption(fluff.Calculator):

    def __init__(self, field='actual_consumption'):
        super(PPSConsumption, self).__init__()
        self.field = field

    @fluff.date_emitter
    def total(self, form):
        for product in form.form['products']:
            if 'real_date' in form.form and form.form['real_date'] and 'product_name' in product:
                yield {
                    'date': real_date(form),
                    'value': product[self.field],
                    'group_by': [product['product_name']]
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
        for product in form.form['products']:
            if 'real_date' in form.form and form.form['real_date'] and 'product_name' in product:
                yield {
                    'date': real_date(form),
                    "value": product['old_stock_total'],
                    "group_by": [product['product_name']]
                }

    @fluff.date_emitter
    def total_stock(self, form):
        for product in form.form['products']:
            if 'real_date' in form.form and form.form['real_date'] and 'product_name' in product:
                yield {
                    'date': real_date(form),
                    "value": product['total_stock'],
                    "group_by": [product['product_name']]
                }

    @fluff.date_emitter
    def livraison(self, form):
        for product in form.form['products']:
            if 'real_date' in form.form and form.form['real_date'] and 'product_name' in product:
                yield {
                    'date': real_date(form),
                    "value": product['top_up']['transfer']['entry']['value']['@quantity'],
                    "group_by": [product['product_name']]
                }

    @fluff.date_emitter
    def display_total_stock(self, form):
        for product in form.form['products']:
            if 'real_date' in form.form and form.form['real_date'] and 'product_name' in product:
                yield {
                    'date': real_date(form),
                    "value": product['display_total_stock'],
                    "group_by": [product['product_name']]
                }

    @fluff.date_emitter
    def old_stock_pps(self, form):
        for product in form.form['products']:
            if 'real_date' in form.form and form.form['real_date'] and 'product_name' in product:
                yield {
                    'date': real_date(form),
                    "value": product['old_stock_pps'],
                    "group_by": [product['product_name']]
                }


    @fluff.date_emitter
    def outside_receipts_amount(self, form):
        for product in form.form['products']:
            if 'real_date' in form.form and form.form['real_date'] and 'product_name' in product:
                yield {
                    "date": real_date(form),
                    "value": product['outside_receipts_amt'],
                    "group_by": [product['product_name']]
                }

    @fluff.date_emitter
    def actual_consumption(self, form):
        for product in form.form['products']:
            if 'real_date' in form.form and form.form['real_date'] and 'product_name' in product:
                yield {
                    'date': real_date(form),
                    "value": product['actual_consumption'],
                    "group_by": [product['product_name']]
                }

    @fluff.date_emitter
    def billed_consumption(self, form):
        for product in form.form['products']:
            if 'real_date' in form.form and form.form['real_date'] and 'product_name' in product:
                yield {
                    'date': real_date(form),
                    "value": product['billed_consumption'],
                    "group_by": [product['product_name']]
                }

    @fluff.date_emitter
    def pps_restant(self, form):
        for product in form.form['products']:
            if 'real_date' in form.form and form.form['real_date'] and 'product_name' in product:
                yield {
                    'date': real_date(form),
                    "value": int(product['pps_stock']) if int(product['pps_stock']) >= 0 else 0,
                    "group_by": [product['product_name']]
                }

    @fluff.date_emitter
    def loss_amt(self, form):
        for product in form.form['products']:
            if 'real_date' in form.form and form.form['real_date'] and 'product_name' in product\
                    and product['loss_amt']:
                yield {
                    'date': real_date(form),
                    "value": int(product['loss_amt']),
                    "group_by": [product['product_name']]
                }


class DureeMoyenneLivraison(fluff.Calculator):

    @fluff.date_emitter
    def total(self, form):
        value = form.form['duree_moyenne_livraison'] if form.form['duree_moyenne_livraison'] else 0
        yield {
            'date': form.form['mois_visite'],
            'value': value
        }
