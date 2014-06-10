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
