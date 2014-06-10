from corehq.apps.locations.models import Location
from custom.intrahealth.reports.tableu_de_board_report import TableuDeBoardReport

INTRAHEALTH_DOMAINS = ('ipm-senegal', 'testing-ipm-senegal', 'ct-apr')

OPERATEUR_XMLNSES = (
    'http://openrosa.org/formdesigner/7330597b92db84b1a33c7596bb7b1813502879be',
)

CUSTOM_REPORTS = (
    ('INFORMED PUSH MODEL REPORTS', (
        TableuDeBoardReport,
    )),
)

def get_location_id(form):
    return form.form['location_id']

def get_location_id_by_type(form, type):
    loc = Location.get(form.form['location_id'])
    for loc_id in loc.lineage:
        loc = Location.get(loc_id)
        if unicode(loc.location_type).lower().replace(" ", "") == type:
            return loc._id

def get_real_date(form):
    return form.form['real_date_repeat'] if 'real_date_repeat' in form.form and form.form['real_date_repeat'] else ''