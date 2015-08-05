from collections import defaultdict
import json
import logging
from datetime import timedelta, datetime
from django.conf import settings

from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_noop, ugettext_lazy
from django.http import Http404
from casexml.apps.case.models import CommCareCase
from corehq.apps.hqcase.dbaccessors import get_case_types_for_domain
from corehq.apps.reports.dbaccessors import stale_get_exports
from dimagi.utils.decorators.memoized import memoized
from django_prbac.utils import has_privilege
from corehq import privileges

from corehq.apps.data_interfaces.dispatcher import DataInterfaceDispatcher

from corehq.apps.data_interfaces.interfaces import DataInterface
from corehq.apps.reports.dispatcher import (
    DataDownloadInterfaceDispatcher,
    DataExportInterfaceDispatcher,
)
from corehq.apps.reports.generic import GenericReportView
from corehq.apps.reports.standard import ProjectReportParametersMixin, DatespanMixin
from corehq.apps.reports.models import HQGroupExportConfiguration, \
    FormExportSchema, CaseExportSchema
from corehq.apps.reports.util import datespan_from_beginning
from couchexport.models import SavedExportSchema, Format
from corehq.apps.app_manager.models import get_app, Application


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

    @property
    def can_view_deid(self):
        return has_privilege(self.request, privileges.DEIDENTIFIED_DATA)

    @memoized
    def get_saved_exports(self):
        exports = stale_get_exports(self.domain)
        exports = filter(lambda x: x.type == "form", exports)
        if not self.can_view_deid:
            exports = filter(lambda x: not x.is_safe, exports)
        return sorted(exports, key=lambda x: x.name)

    @property
    def default_datespan(self):
        return datespan_from_beginning(self.domain, self.datespan_default_days, self.timezone)

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


def sizeof_fmt(num):
    for x in ['bytes', 'KB', 'MB', 'GB', 'TB']:
        if num < 1024.0:
            return "%3.1f %s" % (num, x)
        num /= 1024.0


class ExcelExportReport(FormExportReportBase):
    name = ugettext_noop("Export Forms")
    slug = "excel_export_data"
    report_template_path = "reports/reportdata/excel_export_data.html"
    icon = "icon-list-alt"

    @classmethod
    def display_in_dropdown(cls, domain=None, project=None, user=None):
        return True

    def _get_domain_attachments_size(self):
        # hash of app_id, xmlns to size of attachments
        startkey = [self.domain]

        db = Application.get_db()
        view = db.view('attachments/attachments', startkey=startkey,
                       endkey=startkey + [{}], group_level=3, reduce=True,
                       group=True)
        return {(a['key'][1], a['key'][2]): sizeof_fmt(a['value']) for a in view}

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

        size_hash = self._get_domain_attachments_size()

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
        exports = stale_get_exports(self.domain).all()
        exports = filter(lambda x: x.type == "case", exports)
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
        return stale_get_exports(domain, include_docs=False, limit=1).count() > 0

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


class DataExportInterface(GenericReportView):
    base_template = 'reports/reportdata/data_export.html'
    dispatcher = DataExportInterfaceDispatcher
    section_name = "Export Data"

    @property
    def template_context(self):
        context = super(DataExportInterface, self).template_context
        context.update({
            'bulk_download_notice_text': self.bulk_download_notice_text,
            'bulk_export_format': self.bulk_export_format,
            'create_export_view_name': self.create_export_view_name,
            'download_page_url_root': self.download_page_url_root,
            'edit_export_view_name': self.edit_export_view_name,
            'saved_exports': self.saved_exports,
        })
        return context

    @property
    @memoized
    def saved_exports(self):
        exports = [
            self.export_schema.wrap(doc.to_json())
            for doc in filter(lambda x: x.type == self.export_type, stale_get_exports(self.domain))
        ]
        for export in exports:
            export.download_url = (
                self.download_page_url_root + '?export_id=' + export._id
            )
        return sorted(exports, key=lambda x: x.name)

    @property
    def bulk_export_format(self):
        return Format.XLS_2007

    @property
    def bulk_download_notice_text(self):
        raise NotImplementedError

    @property
    def create_export_view_name(self):
        raise NotImplementedError

    @property
    def download_page_url_root(self):
        raise NotImplementedError

    @property
    def edit_export_view_name(self):
        raise NotImplementedError

    @property
    def export_schema(self):
        raise NotImplementedError

    @property
    def export_type(self):
        raise NotImplementedError


class FormExportInterface(DataExportInterface):
    name = ugettext_noop('Export Forms')
    slug = 'forms'

    bulk_download_notice_text = ugettext_noop('Form Export')
    create_export_view_name = 'create_form_export'
    edit_export_view_name = 'edit_custom_export_form'
    export_schema = FormExportSchema
    export_type = 'form'

    @property
    def download_page_url_root(self):
        return FormExportReport.get_url(domain=self.domain)


class CaseExportInterface(DataExportInterface):
    name = ugettext_noop('Export Cases')
    slug = 'cases'

    bulk_download_notice_text = ugettext_noop('Case Export')
    create_export_view_name = 'create_case_export'
    edit_export_view_name = 'edit_custom_export_case'
    export_schema = CaseExportSchema
    export_type = 'case'

    @property
    def download_page_url_root(self):
        return NewCaseExportReport.get_url(domain=self.domain)


class FormExportReport(FormExportReportBase):
    base_template = 'reports/standard/export_download.html'
    report_template_path = 'reports/partials/download_form_export.html'
    name = ugettext_noop('Download Forms')
    section_name = ugettext_noop("Export Data")
    slug = 'form_export'

    dispatcher = DataDownloadInterfaceDispatcher

    @property
    def template_context(self):
        context = super(FormExportReport, self).template_context
        # TODO - seems redundant, cleanup at some point
        context.update({
            'export': self.exports[0],
            'exports': self.exports,
            "use_bulk": len(self.export_ids) > 1,
            "filter_title": ugettext_noop("Export Filters"),
            "back_url": FormExportInterface.get_url(domain=self.domain),
            'additional_params': mark_safe(
                '&'.join('export_id=%(export_id)s' % {
                    'export_id': export_id,
                } for export_id in self.export_ids)
            ),
            'selected_exports_data': self.selected_exports_data,
            'bulk_download_notice_text': ugettext_noop('Form Exports'),
        })
        return context

    @property
    def export_ids(self):
        return self.request.GET.getlist('export_id')

    @property
    def exports(self):
        return [
            SavedExportSchema.get(export_id) for export_id in self.export_ids
        ]

    @property
    def selected_exports_data(self):
        return {
            export._id: {
                'formname': export.name,
                'modulename': export.name,
                'xmlns': export.xmlns if hasattr(export, 'xmlns') else '',
                'exporttype': 'form',
            } for export in self.exports
        }

    @property
    def breadcrumbs(self):
        return [{
            'link': FormExportInterface.get_url(domain=self.domain),
            'title': ugettext_lazy("Form Exports")
        }]


class NewCaseExportReport(CaseExportReport):
    base_template = 'reports/standard/export_download.html'
    report_template_path = 'reports/partials/download_case_export.html'
    name = ugettext_noop('Download Cases')
    section_name = ugettext_noop('Export Data')
    slug = 'case_export'

    dispatcher = DataDownloadInterfaceDispatcher

    @property
    def template_context(self):
        context = super(NewCaseExportReport, self).template_context
        # TODO - seems redundant, cleanup at some point
        context.update({
            'export': self.exports[0],
            # 'exports': self.exports,
            # "use_bulk": len(self.export_ids) > 1,
            'additional_params': mark_safe(
                '&'.join('export_id=%(export_id)s' % {
                    'export_id': export_id,
                } for export_id in self.export_ids)
            ),
            # 'selected_exports_data': self.selected_exports_data,
            # 'bulk_download_notice_text': ugettext_noop('Case Exports'),
        })
        return context

    @property
    def export_ids(self):
        return self.request.GET.getlist('export_id')

    @property
    def exports(self):
        return [
            SavedExportSchema.get(export_id) for export_id in self.export_ids
        ]

    @property
    def selected_exports_data(self):
        return {}
