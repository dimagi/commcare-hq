from __future__ import absolute_import
from __future__ import unicode_literals
from datetime import datetime, timedelta
from couchdbkit import ResourceNotFound
from django.utils.translation import ugettext_noop
from sqlagg.base import AliasColumn
from sqlagg.columns import SimpleColumn
from sqlagg.filters import EQ, IN
from corehq.apps.groups.models import Group
from corehq.apps.reports.datatables import DTSortType
from corehq.apps.reports.sqlreport import DatabaseColumn, AggregateColumn, SqlTabularReport, DataFormatter, \
    TableDataFormat
from corehq.apps.reports.util import get_INFilter_bindparams
from corehq.util.dates import iso_string_to_datetime
from custom.succeed.reports.patient_interactions import PatientInteractionsReport
from custom.succeed.reports.patient_task_list import PatientTaskListReport
from custom.utils.utils import clean_IN_filter_value
from memoized import memoized
from corehq.apps.cloudcare.api import get_cloudcare_app
from corehq.apps.cloudcare.utils import webapps_module_case_form
from corehq.apps.reports.standard import CustomProjectReport, ProjectReportParametersMixin
from django.utils import html
from custom.succeed.reports import EMPTY_FIELD, CM7, CM_APP_CM_MODULE, OUTPUT_DATE_FORMAT
from custom.succeed.utils import is_succeed_admin, SUCCEED_CM_APPNAME, has_any_role, get_app_build, SUCCEED_DOMAIN


def target_date(visit_name, visit_days, randomization_date):
        if visit_name != 'last':
            tg_date = ((randomization_date + timedelta(days=int(visit_days))) - datetime.utcnow().date()).days
            if tg_date >= 7:
                output_html = (randomization_date + timedelta(days=int(visit_days))).strftime("%m/%d/%Y")
            elif 7 > tg_date > 0:
                output_html = "<span style='background-color: #FFFF00;padding: " \
                              "5px;display: block;'> In %s day(s)</span>" % tg_date
            elif tg_date == 0:
                output_html = "<span style='background-color: #FFFF00;padding: " \
                              "5px;display: block;'>Today</span>"
            else:
                output_html = "<span style='background-color: #FF0000; color: white;padding: " \
                              "5px;display: block;'>%s day(s) overdue</span>" % (tg_date * (-1))
        else:
            output_html = EMPTY_FIELD
            tg_date = -1000000
        return {
            'html': output_html,
            'sort_key': tg_date * (-1)
        }


def date_format(date_str):
    """
    >>> date_format('2015-02-10 11:54:24')
    '02/10/2015'
    >>> date_format('2015-02-10 11:54:24.004000')
    '02/10/2015'

    """
    if date_str:
        # this comes in with a ' ' instead of 'T' for some reason
        # would be nice to go back and figure out where that happens
        # probably `date_str = unicode(dt)` happens somewhere
        if ' ' in date_str and not date_str.endswith('Z'):
            date_str = date_str.replace(' ', 'T') + 'Z'

        date = iso_string_to_datetime(date_str)
        return date.strftime(OUTPUT_DATE_FORMAT)
    else:
        return EMPTY_FIELD


def group_name(owner_id):
    view_results = Group.by_user_id(owner_id, wrap=False)
    if view_results:
        return view_results[0]['value']
    else:
        try:
            return Group.get(owner_id).name
        except ResourceNotFound:
            return "No Group"


def edit_link(case_id, app_dict, latest_build):
    module = app_dict['modules'][CM_APP_CM_MODULE]
    form_idx = [ix for (ix, f) in enumerate(module['forms']) if f['xmlns'] == CM7][0]
    return html.mark_safe("<a target='_blank' class='ajax_dialog' href='%s'>Edit</a>") \
        % html.escape(webapps_module_case_form(domain=app_dict['domain'],
                                               app_id=latest_build,
                                               module_id=CM_APP_CM_MODULE,
                                               form_id=form_idx,
                                               case_id=case_id))


def case_link(name, case_id):
    url = html.escape(
        PatientInteractionsReport.get_url(*[SUCCEED_DOMAIN]) + "?patient_id=%s" % case_id)
    if url:
        return {
            'html': html.mark_safe("<a class='ajax_dialog' href='%s' "
                                   "target='_blank'>%s</a>" % (url, html.escape(name))),
            'sort_key': name
        }
    else:
        return "%s (bad ID format)" % name


def tasks(case_id):
    url = html.escape(
        PatientTaskListReport.get_url(*[SUCCEED_DOMAIN]) +
        "?patient_id=%s&task_status=open" % case_id)
    if url:
        return html.mark_safe("<a class='ajax_dialog' href='%s' target='_blank'>Tasks</a>" % url)
    else:
        return "%s (bad ID format)" % case_id


class PatientListReport(SqlTabularReport, CustomProjectReport, ProjectReportParametersMixin):

    name = ugettext_noop('Patient List')
    slug = 'patient_list'
    use_datatables = True
    table_name = 'fluff_UCLAPatientFluff'
    base_template = 'succeed/base_template.html'
    report_template_path = 'succeed/ucla_table.html'

    fields = ['custom.succeed.fields.CareSite',
              'custom.succeed.fields.PatientStatus']

    @classmethod
    def show_in_navigation(cls, domain=None, project=None, user=None):
        if domain and project and user is None:
            return True
        if user and (is_succeed_admin(user) or has_any_role(user)):
            return True
        return False

    @property
    @memoized
    def rendered_report_title(self):
        return self.name

    @property
    def config(self):
        patient_status = self.request.GET.get('patient_status', None)
        cate_site = self.request.GET.get('care_site_display')
        is_active = None
        if patient_status:
            is_active = 'True' if patient_status == 'active' else 'False'

        owner_ids = []
        user = self.request.couch_user
        if not user.is_web_user():
            owner_ids = [user._id] + user.get_group_ids()

        return {
            'domain': self.domain,
            'is_active': is_active,
            'care_site': cate_site.lower() if cate_site else None,
            'owner_id': tuple(owner_ids)
        }

    @property
    def filters(self):
        filters = [EQ('domain', 'domain')]
        if 'is_active' in self.config and self.config['is_active']:
            filters.append(EQ('is_active', 'is_active'))
        if 'care_site' in self.config and self.config['care_site']:
            filters.append(EQ('care_site', 'care_site'))
        if 'owner_id' in self.config and self.config['owner_id']:
            filters.append(IN('owner_id', get_INFilter_bindparams('owner_id', self.config['owner_id'])))
        return filters

    @property
    def filter_values(self):
        return clean_IN_filter_value(super(PatientListReport, self).filter_values, 'owner_id')

    @property
    def columns(self):
        app_dict = get_cloudcare_app(SUCCEED_DOMAIN, SUCCEED_CM_APPNAME)
        latest_build = get_app_build(app_dict)
        return [
            DatabaseColumn('Modify Schedule', SimpleColumn('doc_id', alias='case_id'),
                           format_fn=lambda x: edit_link(x, app_dict, latest_build)),
            AggregateColumn('Name', aggregate_fn=case_link,
                            columns=[SimpleColumn('name'), AliasColumn('case_id')], sort_type=''),
            DatabaseColumn('MRN', SimpleColumn('mrn')),
            DatabaseColumn('Randomization Date', SimpleColumn('date', alias='rand_date')),
            DatabaseColumn('Visit Name', SimpleColumn('visit_name', alias='vis_name')),
            AggregateColumn('Target Date',
                            aggregate_fn=target_date,
                            columns=[
                                AliasColumn('vis_name'),
                                SimpleColumn('visit_days'),
                                AliasColumn('rand_date')
                            ], sort_type=DTSortType.NUMERIC),
            DatabaseColumn('Most Recent', SimpleColumn('bp_category')),
            DatabaseColumn('Last Interaction Date', SimpleColumn('last_interaction'), format_fn=date_format),
            DatabaseColumn('Tasks', AliasColumn('case_id'), format_fn=tasks),
            DatabaseColumn('Care Team', SimpleColumn('owner_id'), format_fn=group_name)
        ]

    @property
    def group_by(self):
        return ['case_id', 'name', 'mrn', 'rand_date', 'vis_name', 'visit_days', 'bp_category',
                'last_interaction', 'owner_id']

    @property
    def rows(self):
        formatter = DataFormatter(TableDataFormat(self.columns, no_value=self.no_value))
        return formatter.format(self.data, keys=self.keys, group_by=self.group_by)

