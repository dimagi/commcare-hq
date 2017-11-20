from __future__ import absolute_import
import logging
import re

from django.utils.dateformat import format

from couchdbkit.exceptions import ResourceNotFound

from dimagi.utils.dates import force_to_datetime

from corehq.apps.locations.models import get_location, SQLLocation
from corehq.apps.products.models import SQLProduct
from corehq.apps.users.models import CouchUser, CommCareUser
from corehq.fluff.calculators.xform import FormPropertyFilter, IN
from corehq.util.translation import localize
from custom.intrahealth import PRODUCT_MAPPING, PRODUCT_NAMES
import six


def get_products(form, property):
    products = []
    if 'products' not in form.form:
        return

    if not isinstance(form.form['products'], list):
        return

    for product in form.form['products']:
        if property in product:
            products.append(product[property])
    return products


def get_products_id(form, property):
    products = []
    if 'products' not in form.form:
        return

    if not isinstance(form.form['products'], list):
        return

    for product in form.form['products']:
        if property not in product:
            continue
        k = PRODUCT_NAMES.get(product[property].lower())
        if k is not None:
            try:
                code = SQLProduct.active_objects.get(name__iexact=k,
                                                     domain=get_domain(form)).product_id
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


def get_rupture_products_ids(form):
    result = []
    for k, v in form.form.iteritems():
        if re.match("^rupture.*hv$", k):
            product_name = PRODUCT_NAMES.get(PRODUCT_MAPPING[k[8:-3]].lower())
            if product_name is not None:
                try:
                    prd = SQLProduct.active_objects.get(name__iexact=product_name,
                                                        domain=get_domain(form))
                    result.append(prd.product_id)
                except SQLProduct.DoesNotExist:
                    pass
    return result


def _get_location(form):
    loc_id = form.form.get('location_id')
    if loc_id:
        try:
            return get_location(loc_id)
        except SQLLocation.DoesNotExist:
            logging.info('Location %s Not Found.' % loc_id)
    else:
        user_id = form['auth_context']['user_id']
        if not user_id:
            return None
        try:
            user = CouchUser.get_by_user_id(user_id)
            if isinstance(user, CommCareUser):
                return user.location
        except ResourceNotFound:
            logging.info('Location for user %s Not Found.' % user_id)


def get_domain(form):
    return form.domain


def get_prod_info(prod, property):
    return prod[property]


def get_location_id(form):
    loc = _get_location(form)
    if not loc:
        return None
    return loc.location_id


def get_location_id_by_type(form, type):
    try:
        loc = get_location_by_type(form, type)
    except SQLLocation.DoesNotExist:
        loc = None
    return loc.location_id if loc else None


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
        loc = loc[0]
        if type == 'district':
            return loc
    for loc_id in loc.lineage:
        loc = get_location(loc_id)
        if six.text_type(loc.location_type_name).lower().replace(" ", "") == type:
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
                self.operator(self.property_value, form.get_data(self.property_path))
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
