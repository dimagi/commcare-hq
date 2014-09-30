import re
from dimagi.utils.dates import force_to_datetime
from corehq.apps.commtrack.models import CommTrackUser
from corehq.apps.locations.models import Location
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumnGroup, DataTablesColumn
from corehq.apps.reports.sqlreport import DataFormatter, DictDataFormat
from corehq.fluff.calculators.xform import FormPropertyFilter, IN
from corehq.util.translation import localize
from custom.intrahealth.reports.fiche_consommation_report import FicheConsommationReport
from custom.intrahealth.reports.recap_passage_report import RecapPassageReport
from custom.intrahealth.reports.tableu_de_board_report import TableuDeBoardReport

from django.utils.dateformat import format

INTRAHEALTH_DOMAINS = ('ipm-senegal', 'testing-ipm-senegal', 'ct-apr')

OPERATEUR_XMLNSES = (
    'http://openrosa.org/formdesigner/7330597b92db84b1a33c7596bb7b1813502879be',
)

COMMANDE_XMLNSES = (
    'http://openrosa.org/formdesigner/9ED66735-752D-4C69-B9C8-77CEDAAA0348',
    'http://openrosa.org/formdesigner/12b412390011cb9b13406030ab10447ffd99bdf8',
)

RAPTURE_XMLNSES = (
    'http://openrosa.org/formdesigner/AD88DE3E-6AFC-48A5-8BEC-092419C1D45A',
)

LIVRAISON_XMLNSES = ("http://openrosa.org/formdesigner/182649A1-A3BB-4F56-988C-2C103DBAA6D7", )


CUSTOM_REPORTS = (
    ('INFORMED PUSH MODEL REPORTS', (
        TableuDeBoardReport,
        FicheConsommationReport,
        RecapPassageReport
    )),
)

PRODUCT_MAPPING = {
    "collier": "Collier",
    "cu": "CU",
    "depoprovera": "Depo-Provera",
    "diu": "DIU",
    "jadelle": "Jadelle",
    "microgynon": "Microgynon/Lof.",
    "microlut": "Microlut/Ovrette",
    "preservatif_feminin": "Preservatif Feminin",
    "preservatif_masculin": "Preservatif Masculin"
}

def get_products(form, property):
    products = []
    if 'products' in form.form:
        for product in form.form['products']:
            if property in product:
                products.append(product[property])
    return products

def get_rupture_products(form):
    result = []
    for k, v in form.form.iteritems():
        if re.match("^rupture.*hv$", k):
            result.append(PRODUCT_MAPPING[k[8:-3]])
    return result

def _get_location(form):
    if 'location_id' in form.form:
        loc_id = form.form['location_id']
        loc = Location.get(loc_id)
    else:
        user_id = form['auth_context']['user_id']
        if not user_id:
            return None
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
    loc = get_location_by_type(form, type)
    return loc._id if loc else None

def get_location_by_type(form, type):
    loc = _get_location(form)
    if not loc:
        return None

    for loc_id in loc.lineage:
        loc = Location.get(loc_id)
        if unicode(loc.location_type).lower().replace(" ", "") == type:
            return loc

def get_real_date(form):
    date = ""
    if 'real_date' in form.form:
        date = form.form['real_date']
    return date


def format_date_string(value):
    if not value:
        return value
    with localize('fr'):
        return format(force_to_datetime(value), 'd E')


class IsExistFormPropertyFilter(FormPropertyFilter):

    def __init__(self, xmlns=None, property_path=None, property_value=None):
        super(IsExistFormPropertyFilter, self).__init__(xmlns=xmlns, property_path=property_path,
                                                        property_value=property_value, operator=IN)

    def filter(self, form):
        return (
            form.xmlns == self.xmlns and (
                self.property_path is None or
                self.operator(self.property_value, form.xpath(self.property_path))
            )
        )