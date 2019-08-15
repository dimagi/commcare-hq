# coding=utf-8
from __future__ import absolute_import
from __future__ import unicode_literals
import datetime
import logging
import re

from dateutil.relativedelta import relativedelta
from django.utils.dateformat import format
from django.utils.functional import cached_property

from couchdbkit.exceptions import ResourceNotFound

from dimagi.utils.dates import force_to_datetime

from corehq.apps.locations.models import get_location, SQLLocation
from corehq.apps.products.models import SQLProduct
from corehq.apps.reports.datatables import DataTablesHeader
from corehq.apps.reports.standard import CustomProjectReport, ProjectReportParametersMixin
from corehq.apps.users.models import CouchUser, CommCareUser
from corehq.fluff.calculators.xform import FormPropertyFilter, IN
from corehq.util.translation import localize
from custom.intrahealth import PRODUCT_MAPPING, PRODUCT_NAMES
import six


COMMANDE_COMBINED = 'commande_combined'
LIVRAISON_COMBINED = 'livraison_combined'
OPERATEUR_COMBINED = 'operateur_combined'
RAPTURE_COMBINED = 'rapture_combined'
RECOUVREMENT_COMBINED = 'recouvrement_combined'
YEKSI_NAA_REPORTS_VISITE_DE_L_OPERATOUR = 'yeksi_naa_reports_visite_de_l_operateur'
YEKSI_NAA_REPORTS_VISITE_DE_L_OPERATOUR_PER_PRODUCT = "yeksi_naa_reports_visite_de_l_operateur_per_product"
YEKSI_NAA_REPORTS_VISITE_DE_L_OPERATOUR_PER_PROGRAM = "yeksi_naa_reports_visite_de_l_operateur_per_program"
YEKSI_NAA_REPORTS_LOGISTICIEN = 'yeksi_naa_reports_logisticien'


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
    for k, v in six.iteritems(form.form):
        if re.match("^rupture.*hv$", k):
            result.append(PRODUCT_MAPPING[k[8:-3]])
    return result


def get_rupture_products_ids(form):
    result = []
    for k, v in six.iteritems(form.form):
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
        user_id = form.user_id
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


class YeksiNaaLocationMixin(object):

    @cached_property
    def location(self):
        if self.request.GET.get('location_id'):
            return get_location(self.request.GET.get('location_id'))


class YeksiNaaReportConfigMixin(object):

    def config_update(self, config):
        if self.request.GET.get('location_id', ''):
            if self.location.location_type_name.lower() == 'pps':
                config.update(dict(pps_id=self.location.location_id))
            elif self.location.location_type_name.lower() == 'district':
                config.update(dict(district_id=self.location.location_id))
            else:
                config.update(dict(region_id=self.location.location_id))

    @property
    def report_config(self):
        config = dict(
            domain=self.domain,
        )
        if self.request.GET.get('month_start'):
            startdate = datetime.datetime(
                year=int(self.request.GET.get('year_start')),
                month=int(self.request.GET.get('month_start')),
                day=1,
                hour=0,
                minute=0,
                second=0
            )
            enddate = datetime.datetime(
                year=int(self.request.GET.get('year_end')),
                month=int(self.request.GET.get('month_end')),
                day=1,
                hour=23,
                minute=59,
                second=59
            )
            enddate = enddate + relativedelta(months=1) - relativedelta(days=1)
        else:
            startdate = datetime.datetime.now()
            startdate.replace(month=1, day=1, hour=0, minute=0, second=0)
            enddate = datetime.datetime.now()
            enddate.replace(day=1, hour=23, minute=59, second=59)
            enddate = startdate + relativedelta(month=1) - relativedelta(day=1)
        config['startdate'] = startdate
        config['enddate'] = enddate
        config['program'] = self.request.GET.get('program')
        self.config_update(config)
        return config


class YeksiNaaMixin(YeksiNaaLocationMixin, YeksiNaaReportConfigMixin):
    data_source = None

    @property
    def headers(self):
        return DataTablesHeader()

    @property
    def rows(self):
        return []


class MultiReport(CustomProjectReport, YeksiNaaMixin, ProjectReportParametersMixin):

    title = ''
    report_template_path = "yeksi_naa/multi_report.html"
    flush_layout = True
    export_format_override = None

    @cached_property
    def rendered_report_title(self):
        return self.title

    @cached_property
    def data_providers(self):
        return []

    @property
    def report_context(self):
        context = {
            'reports': [self.get_report_context(dp) for dp in self.data_providers],
            'title': self.title
        }

        return context

    def get_report_context(self, data_provider):

        total_row = []
        self.data_source = data_provider
        if self.needs_filters:
            headers = []
            rows = []
        else:
            headers = data_provider.headers
            rows = data_provider.rows
            total_row = data_provider.total_row

        context = dict(
            report_table=dict(
                title=data_provider.title,
                slug=data_provider.slug,
                comment=data_provider.comment,
                headers=headers,
                rows=rows,
                total_row=total_row,
                default_rows=self.default_rows,
                datatables=data_provider.datatables,
                fix_column=data_provider.fix_left_col
            )
        )

        return context

    @property
    def export_table(self):
        export_tables = []
        for individual_report in self.report_context['reports']:
            report_table = individual_report['report_table']
            extracted_rows = self._sanitize_all_rows(report_table)
            extracted_total_row = self._sanitize_single_row(report_table['total_row'])
            export_tables.append(self._export_table(report_table['title'],
                                                    report_table['headers'],
                                                    extracted_rows, extracted_total_row))
        return export_tables

    def _sanitize_all_rows(self, report_table):
        extracted_rows = []
        for row in report_table['rows']:
            extracted_rows.append(self._sanitize_single_row(row))
        return extracted_rows

    @staticmethod
    def _sanitize_single_row(row):
        extracted_row_values = []
        for row_value in row:
            if isinstance(row_value, dict):
                # If keys are dicts, they contain html info (ie: row_value = {'html': 'title'})
                extracted_row_values.append(row_value['html'])
            else:
                extracted_row_values = row
                break
        return extracted_row_values

    def _export_table(self, export_sheet_name, headers, formatted_rows, total_row=None):
        def _unformat_row(row):
            return [col.get("sort_key", col) if isinstance(col, dict) else col for col in row]

        table = headers.as_export_table
        rows = [_unformat_row(row) for row in formatted_rows]
        replace = ''

        # make headers and subheaders consistent
        for k, v in enumerate(table[0]):
            if v != ' ':
                replace = v
            else:
                table[0][k] = replace
        table.extend(rows)
        if total_row:
            table.append(_unformat_row(total_row))

        return [export_sheet_name, table]
