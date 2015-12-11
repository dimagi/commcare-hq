from collections import defaultdict
import logging
from datetime import timedelta, datetime
from django.conf import settings

from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_noop, ugettext_lazy
from django.http import Http404
from corehq.apps.hqcase.dbaccessors import get_case_types_for_domain
from corehq.apps.reports.dbaccessors import stale_get_export_count
from corehq.couchapps.dbaccessors import get_attachment_size_by_domain
from dimagi.utils.decorators.memoized import memoized
from django_prbac.utils import has_privilege
from corehq import privileges

from corehq.apps.data_interfaces.dispatcher import DataInterfaceDispatcher

from corehq.apps.data_interfaces.interfaces import DataInterface
from corehq.apps.reports.generic import GenericReportView
from corehq.apps.reports.standard import ProjectReportParametersMixin, DatespanMixin
from corehq.apps.reports.models import HQGroupExportConfiguration, \
    FormExportSchema, CaseExportSchema
from corehq.apps.reports.util import datespan_from_beginning
from couchexport.models import SavedExportSchema, Format
from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.app_manager.models import Application


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
    fields = ['corehq.apps.reports.filters.users.UserTypeFilter',
              'corehq.apps.reports.filters.select.GroupFilter',
              'corehq.apps.reports.filters.dates.DatespanFilter']

    @memoized
    def get_saved_exports(self):
        from corehq.apps.export.views import user_can_view_deid_exports
        exports = FormExportSchema.get_stale_exports(self.domain)
        if not user_can_view_deid_exports(self.domain, self.request.couch_user):
            exports = filter(lambda x: not x.is_safe, exports)
        return sorted(exports, key=lambda x: x.name)

    @property
    def default_datespan(self):
        return datespan_from_beginning(self.domain, self.timezone)

    def get_filter_params(self):
        params = self.request.GET.copy()
        if self.datespan.startdate_display:  # when no forms have been submitted to a domain, this defaults to None
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

    @classmethod
    def display_in_dropdown(cls, domain=None, project=None, user=None):
        return True

    def properties(self, size_hash):
        properties = dict()
        exports = self.get_saved_exports()

        for export in exports:
            for table in export.tables:
                properties[export.name] = {
                    'xmlns': export.index[1],
                    'export_id': export._id,
                    'size': size_hash.get((export.app_id, export.index[1]), None),
                }

        return properties

    @property
    def report_context(self):
        # This map for this view emits twice, once with app_id and once with {}, letting you join across all app_ids.
        # However, we want to separate out by (app_id, xmlns) pair not just xmlns so we use [domain] to [domain, {}]
        forms = []
        unknown_forms = []
        startkey = [self.domain]
        db = Application.get_db()  # the view emits from both forms and applications

        size_hash = get_attachment_size_by_domain(self.domain)

        for f in db.view('exports_forms/by_xmlns',
                         startkey=startkey, endkey=startkey + [{}], group=True,
                         stale=settings.COUCH_STALE_QUERY):
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
            if 'id' in form['app']:
                key = (form['app']['id'], form['xmlns'])
            else:
                key = None
            if key in size_hash:
                form['size'] = size_hash[key]
            else:
                form['size'] = None
            forms.append(form)

        if unknown_forms:
            apps = db.view('exports_forms/by_xmlns',
                startkey=['^Application', self.domain],
                endkey=['^Application', self.domain, {}],
                reduce=False,
                stale=settings.COUCH_STALE_QUERY,
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
                    key = (None, form['xmlns'])
                    form['size'] = size_hash.get(key, None)

        def _sortkey(form):
            app_id = form['app']['id']
            if form['has_app']:
                order = 0 if not form.get('app_deleted') else 1
                app_name = form['app']['name']
                module = form.get('module')
                if module:
                    # module is sometimes wrapped json, sometimes a dict!
                    module_id = module['id'] if 'id' in module else module.id
                else:
                    module_id = -1 if form.get('is_user_registration') else 1000
                app_form = form.get('form')
                if app_form:
                    # app_form is sometimes wrapped json, sometimes a dict!
                    form_id = app_form['id'] if 'id' in app_form else app_form.id
                else:
                    form_id = -1
                return (order, app_name, app_id, module_id, form_id)
            else:
                form_xmlns = form['xmlns']
                return (2, form_xmlns, app_id)

        forms = sorted(forms, key=_sortkey)
        # if there is a custom group export defined grab it here
        groups = HQGroupExportConfiguration.by_domain(self.domain)
        context = super(ExcelExportReport, self).report_context

        # Check if any custom exports are in the size hash
        saved_exports_has_media = any((e.app_id, e.index[1]) in size_hash for e in context['saved_exports'])

        context.update(
            forms=forms,
            edit=self.request.GET.get('edit') == 'true',
            group_exports=[group.form_exports for group in groups
                if group.form_exports],
            group_export_cutoff=datetime.utcnow() - timedelta(days=settings.SAVED_EXPORT_ACCESS_CUTOFF),
            report_slug=self.slug,
            property_hash=self.properties(size_hash),
            exports_has_media=size_hash,
            saved_exports_has_media=saved_exports_has_media
        )
        return context


class CaseExportReport(ExportReport):
    name = ugettext_lazy("Export Cases")
    slug = "case_export"
    fields = ['corehq.apps.reports.filters.users.UserTypeFilter',
              'corehq.apps.reports.filters.select.GroupFilter']
    report_template_path = "reports/reportdata/case_export_data.html"
    icon = "icon-share"

    @classmethod
    def display_in_dropdown(cls, domain=None, project=None, user=None):
        return True

    def get_filter_params(self):
        return self.request.GET.copy()

    def get_saved_exports(self):
        exports = CaseExportSchema.get_stale_exports(self.domain)
        return sorted(exports, key=lambda x: x.name)

    @property
    def report_context(self):
        context = super(CaseExportReport, self).report_context
        case_types = get_case_types_for_domain(self.domain)
        groups = HQGroupExportConfiguration.by_domain(self.domain)
        context.update(
            case_types=case_types,
            group_exports=[group.case_exports for group in groups
                           if group.case_exports],
            report_slug=self.slug,
        )
        context['case_format'] = self.request.GET.get('case_format') or 'csv'
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
    name = ugettext_lazy("De-Identified Export")
    report_template_path = 'reports/reportdata/form_deid_export.html'

    @classmethod
    def show_in_navigation(cls, domain=None, project=None, user=None):
        return stale_get_export_count(domain) > 0

    def get_saved_exports(self):
        return filter(lambda export: export.is_safe, super(DeidExportReport, self).get_saved_exports())

    @property
    def report_context(self):
        context = super(DeidExportReport, self).report_context
        context.update(
            ExcelExportReport_name=ExcelExportReport.name,
            is_deid_form_report=True
        )
        return context

    def get_filter_params(self):
        params = super(DeidExportReport, self).get_filter_params()
        params['deid'] = 'true'
        return params

    @classmethod
    def get_subpages(self):
        return []
