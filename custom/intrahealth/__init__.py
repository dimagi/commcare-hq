import logging
import re
from corehq.apps.products.models import SQLProduct
from dimagi.utils.dates import force_to_datetime
from couchdbkit.exceptions import ResourceNotFound
from corehq.apps.users.models import CommCareUser
from corehq.apps.locations.models import Location, SQLLocation
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

RECOUVREMENT_XMLNSES = ('http://openrosa.org/formdesigner/61478ca7d20e8e1fa2fd110b1b2b4d46bb5b6b9c',
                        'http://openrosa.org/formdesigner/c03317d26979ba4b656fac23ef1f03dfe4337b1d')

CUSTOM_REPORTS = (
    ('INFORMED PUSH MODEL REPORTS', (
        TableuDeBoardReport,
        FicheConsommationReport,
        RecapPassageReport
    )),
)

_PRODUCT_NAMES = {
    u'diu': [u"diu"],
    u'jadelle': [u"jadelle"],
    u'depo-provera': [u"d\xe9po-provera", u"depo-provera"],
    u'microlut/ovrette': [u"microlut/ovrette"],
    u'microgynon/lof.': [u"microgynon/lof."],
    u'preservatif masculin': [u"pr\xe9servatif masculin", u"preservatif masculin", u"preservatif_masculin"],
    u'preservatif feminin': [u"pr\xe9servatif f\xe9minin", u"preservatif feminin", u"preservatif_feminin"],
    u'cu': [u"cu"],
    u'collier': [u"collier"]
}

PRODUCT_NAMES = {v: k for k, values in _PRODUCT_NAMES.iteritems() for v in values}

PRODUCT_MAPPING = {
    "collier": "Collier",
    "cu": "CU",
    "depoprovera": "Depo-Provera",
    "diu": "DIU",
    "jadelle": "Jadelle",
    "microgynon": "Microgynon/Lof.",
    "microlut": "Microlut/Ovrette",
    "preservatif_feminin": "Preservatif Feminin",
    "preservatif_masculin": "Preservatif Masculin",
    "sayana_press": "Sayana Press"
}


def get_products(form, property):
    products = []
    if 'products' in form.form:
        for product in form.form['products']:
            if property in product:
                products.append(product[property])
    return products


def get_products_code(form, property):
    products = []
    if 'products' in form.form:
        for product in form.form['products']:
            if property in product:
                k = PRODUCT_NAMES.get(product[property].lower())
                if k is not None:
                    try:
                        code = SQLProduct.objects.get(name__iexact=k,
                                                      domain=get_domain(form)).code
                        products.append(code)
                    except SQLProduct.DoesNotExist:
                        pass
    return products


def get_rupture_products(form):
    result = []
    for k, v in form.form.iteritems():
        if re.match("^rupture.*hv$", k):
            result.append(PRODUCT_MAPPING[k[8:-3]])
    return result


def get_rupture_products_code(form):
    result = []
    for k, v in form.form.iteritems():
        if re.match("^rupture.*hv$", k):
            product_name = PRODUCT_NAMES.get(PRODUCT_MAPPING[k[8:-3]].lower())
            if product_name is not None:
                try:
                    prd = SQLProduct.objects.get(name__iexact=product_name,
                                                 domain=get_domain(form))
                    result.append(prd.code)
                except SQLProduct.DoesNotExist:
                    pass
    return result


def _get_location(form):
    loc = None
    if form.form.get('location_id'):
        loc_id = form.form['location_id']
        try:
            loc = Location.get(loc_id)
        except ResourceNotFound:
            logging.info('Location %s Not Found.' % loc_id)
    else:
        user_id = form['auth_context']['user_id']
        if not user_id:
            return None
        try:
            user = CommCareUser.get(user_id)
            loc = user.location
        except ResourceNotFound:
            logging.info('Location %s Not Found.' % loc)

    return loc


def get_domain(form):
    return form.domain


def get_prod_info(prod, property):
    return prod[property]


def get_location_id(form):
    loc = _get_location(form)
    if not loc:
        return None
    return loc._id


def get_location_id_by_type(form, type):
    try:
        loc = get_location_by_type(form, type)
    except SQLLocation.DoesNotExist:
        loc = None
    return loc._id if loc else None


def get_location_by_type(form, type):
    loc = _get_location(form)
    if not loc:
        district_name = form.form.get('district_name', None)
        loc = SQLLocation.objects.filter(
            domain=get_domain(form),
            name=district_name)
        if not loc:
            return None
        if loc.count() > 1:
            loc = loc.filter(location_type__name='District')
        loc = loc[0].couch_location
        if type == 'district':
            return loc

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


def get_pps_name(form):
    pps_name = form.form.get('PPS_name', None)

    if not pps_name:
        loc = _get_location(form)
        if not loc:
            return None
        return loc.name
    else:
        return pps_name


def get_district_name(form):
    district_name = form.form.get('district_name', None)
    if not district_name:
        loc = get_location_by_type(form, 'district')
        if not loc:
            return None
        return loc.name
    else:
        return district_name


def get_month(form, prop):
    value = form.form.get(prop, '')
    if value:
        with localize('fr'):
            return format(force_to_datetime(value), 'E')
    else:
        return value


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


def get_loc_from_case(case):
    loc = SQLLocation.objects.filter(
        domain=case.get_case_property('domain'),
        name=case.get_case_property('district_name'))
    if loc:
        if loc[0].location_type.name == 'PPS':
            return loc[0].parent
        if loc.count() > 1:
            loc = loc.filter(location_type__name='District')
        return loc[0]


def get_region_id(case):
    loc = get_loc_from_case(case)
    return loc.parent.location_id if loc else None


def get_district_id(case):
    loc = get_loc_from_case(case)
    return loc.location_id if loc else None
