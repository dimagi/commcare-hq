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
    def __init__(self, product_name, *args, **kwargs):
        self.product_name = product_name
        super(Commandes, self).__init__(*args, **kwargs)

    @fluff.date_emitter
    def total(self, form):
        products = form.form['products']
        for product in products:
            if unicode(product['productName']).lower() in self.product_name:
                yield {
                    'date': product['receivedMonthInner'],
                    'value': product['amountOrdered']
                }

class Recus(fluff.Calculator):
    def __init__(self, product_name, *args, **kwargs):
        self.product_name = product_name
        super(Recus, self).__init__(*args, **kwargs)

    @fluff.date_emitter
    def total(self, form):
        products = form.form['products']
        for product in products:
            if unicode(product['productName']).lower() in self.product_name:
                yield {
                    'date': product['receivedMonthInner'],
                    'value': product['amountReceived']
                }

class PPSConsumption(fluff.Calculator):

    def __init__(self, productsName, field='actual_consumption'):
        super(PPSConsumption, self).__init__()
        self.productsName = productsName
        self.field = field

    @fluff.date_emitter
    def total(self, form):
        sum = 0
        for product in form.form['products']:
            if unicode(product['product_name']) in self.productsName:
                sum += int(product[self.field])
        yield {
            'date': form_date(form),
            'value': sum
        }
