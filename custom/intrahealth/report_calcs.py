import fluff
from corehq.apps.locations.models import Location
from custom.intrahealth import get_location_id_by_type


def form_date(form):
    return form.received_on

class PPSRegistered(fluff.Calculator):
    @fluff.date_emitter
    def total(self, form):
        loc = Location.get(get_location_id_by_type(form=form, type=u'r\xe9gion'))
        count = list(Location.filter_by_type(form.domain, 'PPS', loc)).__len__()
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
            yield {
                'date': product['receivedMonthInner'],
                'value': product['amountReceived'],
                'group_by': [product['productName']]
            }

class PPSConsumption(fluff.Calculator):

    def __init__(self, field='actual_consumption'):
        super(PPSConsumption, self).__init__()
        self.field = field

    #TODO Some products has two different names(with and without unicode characters)
    @fluff.date_emitter
    def total(self, form):
        for product in form.form['products']:
            yield {
                'date': form_date(form),
                'value': product[self.field],
                'group_by': [product['product_name']]
            }

class RecapPassage(fluff.Calculator):

    @fluff.date_emitter
    def old_stock_total(self, form):
        for product in form.form['products']:
            yield {
                "date": form_date(form),
                "value": product['old_stock_total'],
                "group_by": [product['product_name']]
            }

    @fluff.date_emitter
    def total_stock(self, form):
        for product in form.form['products']:
            yield {
                "date": form_date(form),
                "value": product['total_stock'],
                "group_by": [product['product_name']]
            }

    @fluff.date_emitter
    def livraison(self, form):
        for product in form.form['products']:
            yield {
                "date": form_date(form),
                "value": product['top_up']['transfer']['entry']['value']['@quantity'],
                "group_by": [product['product_name']]
            }

    @fluff.date_emitter
    def display_total_stock(self, form):
        for product in form.form['products']:
            yield {
                "date": form_date(form),
                "value": product['display_total_stock'],
                "group_by": [product['product_name']]
            }

    @fluff.date_emitter
    def old_stock_pps(self, form):
        for product in form.form['products']:
            yield {
                "date": form_date(form),
                "value": product['old_stock_pps'],
                "group_by": [product['product_name']]
            }


    @fluff.date_emitter
    def outside_receipts_amount(self, form):
        for product in form.form['products']:
            yield {
                "date": form_date(form),
                "value": product['outside_receipts_amt'],
                "group_by": [product['product_name']]
            }

    @fluff.date_emitter
    def actual_consumption(self, form):
        for product in form.form['products']:
            yield {
                "date": form_date(form),
                "value": product['actual_consumption'],
                "group_by": [product['product_name']]
            }

    @fluff.date_emitter
    def billed_consumption(self, form):
        for product in form.form['products']:
            yield {
                "date": form_date(form),
                "value": product['billed_consumption'],
                "group_by": [product['product_name']]
            }

    @fluff.date_emitter
    def pps_restant(self, form):
        for product in form.form['products']:
            yield {
                "date": form_date(form),
                "value": product['billed_consumption'],
                "group_by": [product['product_name']]
            }
