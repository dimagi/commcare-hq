import fluff
from custom.up_nrhm.utils import get_case_property


class Numerator(fluff.Calculator):

    @fluff.null_emitter
    def numerator(self, _):
        yield None


class PropertyCalculator(fluff.Calculator):

    def __init__(self, property_name):
        super(PropertyCalculator, self).__init__()
        self.property_name = property_name

    @fluff.date_emitter
    def total(self, doc):
        yield {
            'date': doc.received_on,
            'value': get_case_property(doc, self.property_name)
        }
