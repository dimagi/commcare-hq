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
        property_value = get_case_property(doc, self.property_name)
        if property_value:
            try:
                value = int(property_value)
                yield {
                    'date': doc.received_on,
                    'value': value
                }
            except ValueError:
                pass
