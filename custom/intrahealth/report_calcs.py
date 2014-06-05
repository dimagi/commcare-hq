import fluff
from corehq.apps.locations.models import Location


def form_date(form):
    return form.form['real_date']


class PPSRegistered(fluff.Calculator):
    @fluff.date_emitter
    def total(self, form):
        locs = len(Location.filter_by_type(form.domain, 'PPS'))
        yield {
            'date': form_date(form),
            'value': locs
        }


class PPSPlaned(fluff.Calculator):
    @fluff.date_emitter
    def total(self, form):
        yield {
            'date': form_date(form),
            'value': 0
        }


class PPSVisited(fluff.Calculator):
    @fluff.date_emitter
    def total(self, form):
        yield {
            'date': form_date(form),
            'value': 0
        }


class PPSSubmitted(fluff.Calculator):
    @fluff.date_emitter
    def total(self, form):
        yield {
            'date': form_date(form),
            'value': 0
        }