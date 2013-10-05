from collections import defaultdict
import json
import logging
import datetime
from django.utils.translation import ugettext_noop
from corehq.apps.data_interfaces.dispatcher import DataInterfaceDispatcher
from corehq.apps.data_interfaces.interfaces import DataInterface
from dimagi.utils.dates import DateSpan
from django.conf import settings
from django.http import Http404
from corehq.apps.reports.standard import ProjectReportParametersMixin, DatespanMixin
from corehq.apps.reports.models import FormExportSchema,\
    HQGroupExportConfiguration
from corehq.apps.reports.util import make_form_couch_key, datespan_from_beginning
from couchexport.models import SavedExportSchema, Format
from dimagi.utils.couch.database import get_db
from corehq.apps.app_manager.models import get_app
from dimagi.utils.parsing import string_to_datetime


class ExportReport(DataInterface, ProjectReportParametersMixin):
    """
        Base class for export reports.
    """
    flush_layout = True
    dispatcher = DataInterfaceDispatcher

    @property
    def custom_bulk_export_format(self):
        return Format.XLS_2007

    @property
    def report_context(self):
        return dict(
            custom_bulk_export_format=self.custom_bulk_export_format,
            saved_exports=self.get_saved_exports(),
            timezone=self.timezone,
            get_filter_params=self.get_filter_params(),
        )


class FormExportReportBase(ExportReport, DatespanMixin):
    fields = ['corehq.apps.reports.fields.FilterUsersField',
              'corehq.apps.reports.fields.GroupField',
              'corehq.apps.reports.fields.DatespanField']

    def get_saved_exports(self):
        # add saved exports. because of the way in which the key is stored
        # (serialized json) this is a little bit hacky, but works.
        startkey = json.dumps([self.domain, ""])[:-3]
        endkey = "%s{" % startkey
        exports = FormExportSchema.view("couchexport/saved_export_schemas",
            startkey=startkey, endkey=endkey,
            include_docs=True)

        exports = filter(lambda x: x.type == "form", exports)
        return exports

    @property
    def default_datespan(self):
        return datespan_from_beginning(self.domain, self.datespan_default_days, self.timezone)

    def get_filter_params(self):
        params = self.request.GET.copy()
        params['startdate'] = self.datespan.startdate_display
        params['enddate'] = self.datespan.enddate_display
        return params

    @classmethod
    def get_subpages(self):
        from corehq.apps.export.views import CreateCustomFormExportView, EditCustomFormExportView
        return [
            {
                'title': CreateCustomFormExportView.page_title,
                'urlname': CreateCustomFormExportView.urlname,
            },
            {
                'title': EditCustomFormExportView.page_title,
                'urlname': EditCustomFormExportView.urlname,
            },
        ]


class ExcelExportReport(FormExportReportBase):
    name = ugettext_noop("Export Forms")
    slug = "excel_export_data"
    report_template_path = "reports/reportdata/excel_export_data.html"
    icon = "icon-list-alt"

    @property
    def report_context(self):
        # This map for this view emits twice, once with app_id and once with {}, letting you join across all app_ids.
        # However, we want to separate out by (app_id, xmlns) pair not just xmlns so we use [domain] to [domain, {}]
        forms = []
        unknown_forms = []
        for f in get_db().view('exports_forms/by_xmlns', startkey=[self.domain], endkey=[self.domain, {}], group=True):
            form = f['value']
            if form.get('app_deleted') and not form.get('submissions'):
                continue
            if 'app' in form:
                form['has_app'] = True
            else:
                app_id = f['key'][1] or ''
                form['app'] = {
                    'id': app_id
                }
                form['has_app'] = False
                form['show_xmlns'] = True
                unknown_forms.append(form)

            form['current_app'] = form.get('app')
            forms.append(form)

        if unknown_forms:
            apps = get_db().view('exports_forms/by_xmlns',
                startkey=['^Application', self.domain],
                endkey=['^Application', self.domain, {}],
                reduce=False,
            )
            possibilities = defaultdict(list)
            for app in apps:
                # index by xmlns
                x = app['value']
                x['has_app'] = True
                possibilities[app['key'][2]].append(x)

            class AppCache(dict):
                def __init__(self, domain):
                    super(AppCache, self).__init__()
                    self.domain = domain

                def __getitem__(self, item):
                    if not self.has_key(item):
                        try:
                            self[item] = get_app(app_id=item, domain=self.domain)
                        except Http404:
                            pass
                    return super(AppCache, self).__getitem__(item)

            app_cache = AppCache(self.domain)

            for form in unknown_forms:
                app = None
                if form['app']['id']:
                    try:
                        app = app_cache[form['app']['id']]
                        form['has_app'] = True
                    except KeyError:
                        form['app_does_not_exist'] = True
                        form['possibilities'] = possibilities[form['xmlns']]
                        if form['possibilities']:
                            form['duplicate'] = True
                    else:
                        if app.domain != self.domain:
                            logging.error("submission tagged with app from wrong domain: %s" % app.get_id)
                        else:
                            if app.copy_of:
                                try:
                                    app = app_cache[app.copy_of]
                                    form['app_copy'] = {'id': app.get_id, 'name': app.name}
                                except KeyError:
                                    form['app_copy'] = {'id': app.copy_of, 'name': '?'}
                            if app.is_deleted():
                                form['app_deleted'] = {'id': app.get_id}
                            try:
                                app_forms = app.get_xmlns_map()[form['xmlns']]
                            except AttributeError:
                                # it's a remote app
                                app_forms = None
                            if app_forms:
                                app_form = app_forms[0]
                                if app_form.doc_type == 'UserRegistrationForm':
                                    form['is_user_registration'] = True
                                else:
                                    app_module = app_form.get_module()
                                    form['module'] = app_module
                                    form['form'] = app_form
                                form['show_xmlns'] = False

                            if not form.get('app_copy') and not form.get('app_deleted'):
                                form['no_suggestions'] = True
                    if app:
                        form['app'] = {'id': app.get_id, 'name': app.name, 'langs': app.langs}

                else:
                    form['possibilities'] = possibilities[form['xmlns']]
                    if form['possibilities']:
                        form['duplicate'] = True
                    else:
                        form['no_suggestions'] = True

        def _sortkey(form):
            if form['has_app']:
                return (
                    0 if not form.get('app_deleted') else 1,
                    form['app']['name'],
                    form['app']['id'],
                    form.get('module', {'id': -1 if form.get('is_user_registration') else 1000})['id'],
                    form.get('form', {'id': -1})['id'],
                )
            else:
                return (
                    2,
                    form['xmlns'],
                    form['app']['id']
                )

        forms = sorted(forms, key=_sortkey)
        # if there is a custom group export defined grab it here
        groups = HQGroupExportConfiguration.by_domain(self.domain)
        context = super(ExcelExportReport, self).report_context
        context.update(
            forms=forms,
            edit=self.request.GET.get('edit') == 'true',
            group_exports=groups
        )
        return context


class CaseExportReport(ExportReport):
    name = ugettext_noop("Export Cases")
    slug = "case_export"
    fields = ['corehq.apps.reports.fields.FilterUsersField',
              'corehq.apps.reports.fields.GroupField']
    report_template_path = "reports/reportdata/case_export_data.html"
    icon = "icon-share"

    def get_filter_params(self):
        return self.request.GET.copy()

    def get_saved_exports(self):
        startkey = json.dumps([self.domain, ""])[:-3]
        endkey = "%s{" % startkey
        exports = SavedExportSchema.view("couchexport/saved_export_schemas",
            startkey=startkey, endkey=endkey,
            include_docs=True).all()
        exports = filter(lambda x: x.type == "case", exports)
        return exports

    @property
    def report_context(self):
        cases = get_db().view("hqcase/types_by_domain",
            startkey=[self.domain],
            endkey=[self.domain, {}],
            reduce=True,
            group=True,
            group_level=2).all()
        context = super(CaseExportReport, self).report_context
        context.update(
            case_types=[case['key'][1] for case in cases],
        )
        return context

    @classmethod
    def get_subpages(self):
        from corehq.apps.export.views import CreateCustomCaseExportView, EditCustomCaseExportView
        return [
            {
                'title': CreateCustomCaseExportView.page_title,
                'urlname': CreateCustomCaseExportView.urlname,
            },
            {
                'title': EditCustomCaseExportView.page_title,
                'urlname': EditCustomCaseExportView.urlname,
            },
        ]


class DeidExportReport(FormExportReportBase):
    slug = 'deid_export'
    name = "De-Identified Export"
    report_template_path = 'reports/reportdata/form_deid_export.html'

    @classmethod
    def show_in_navigation(cls, domain=None, project=None, user=None):
        startkey = json.dumps([domain, ""])[:-3]
        return SavedExportSchema.view("couchexport/saved_export_schemas",
            startkey=startkey,
            limit=1,
            include_docs=False,
            #stale=settings.COUCH_STALE_QUERY,
        ).count() > 0


    def get_saved_exports(self):
        return filter(lambda export: export.is_safe, super(DeidExportReport, self).get_saved_exports())

    @property
    def report_context(self):
        context = super(DeidExportReport, self).report_context
        context.update(
            ExcelExportReport_name=ExcelExportReport.name
        )
        return context

    def get_filter_params(self):
        params = super(DeidExportReport, self).get_filter_params()
        params['deid'] = 'true'
        return params

    @classmethod
    def get_subpages(self):
        return []
