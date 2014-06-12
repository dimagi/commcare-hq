from corehq.apps.commtrack.models import CommTrackUser
from corehq.apps.locations.models import Location
from custom.intrahealth.reports.fiche_consommation_report import FicheConsommationReport
from custom.intrahealth.reports.tableu_de_board_report import TableuDeBoardReport

INTRAHEALTH_DOMAINS = ('ipm-senegal', 'testing-ipm-senegal', 'ct-apr')

OPERATEUR_XMLNSES = (
    'http://openrosa.org/formdesigner/7330597b92db84b1a33c7596bb7b1813502879be',
)

COMMANDE_XMLNSES = (
    'http://openrosa.org/formdesigner/9ED66735-752D-4C69-B9C8-77CEDAAA0348',
    'http://openrosa.org/formdesigner/12b412390011cb9b13406030ab10447ffd99bdf8',
)

CUSTOM_REPORTS = (
    ('INFORMED PUSH MODEL REPORTS', (
        TableuDeBoardReport,
        FicheConsommationReport
    )),
)

def _get_location(form):
    if 'location_id' in form.form:
        loc_id = form.form['location_id']
        loc = Location.get(loc_id)
    else:
        user_id = form['auth_context']['user_id']
        user = CommTrackUser.get(user_id)
        loc = user.location
    return loc

def get_domain(form):
    return form.domain

def get_prod_info(prod, property):
    return prod[property]

def get_location_id(form):
    return _get_location(form)._id

def get_location_id_by_type(form, type):
    loc = _get_location(form)

    for loc_id in loc.lineage:
        loc = Location.get(loc_id)
        if unicode(loc.location_type).lower().replace(" ", "") == type:
            return loc._id

def get_real_date(form):
    return form.form['real_date_repeat'] if 'real_date_repeat' in form.form and form.form['real_date_repeat'] else ''

