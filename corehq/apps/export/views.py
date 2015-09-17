from datetime import datetime, date
from couchdbkit import ResourceNotFound
from django.contrib import messages
from django.core.exceptions import SuspiciousOperation
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, HttpResponseBadRequest, Http404
from django.utils.decorators import method_decorator
import json

from djangular.views.mixins import JSONResponseMixin, allow_remote_invocation
import pytz
from corehq import toggles, privileges
from corehq.apps.app_manager.dbaccessors import get_apps_in_domain
from corehq.apps.app_manager.models import Application
from corehq.apps.app_manager.templatetags.xforms_extras import trans
from corehq.apps.export.custom_export_helpers import make_custom_export_helper
from corehq.apps.export.exceptions import ExportNotFound, ExportAppException
from corehq.apps.export.forms import (
    CreateFormExportForm,
    CreateCaseExportForm,
    FilterFormExportDownloadForm,
    FilterCaseExportDownloadForm,
    ExportFormValidationException,
)
from corehq.apps.groups.models import Group
from corehq.apps.reports.dbaccessors import touch_exports
from corehq.apps.reports.display import xmlns_to_name
from corehq.apps.reports.exportfilters import default_form_filter
from corehq.apps.reports.models import FormExportSchema, CaseExportSchema
from corehq.apps.reports.standard.export import (
    CaseExportReport,
    ExcelExportReport,
)
from corehq.apps.reports.util import datespan_from_beginning
from corehq.apps.settings.views import BaseProjectDataView
from corehq.apps.style.decorators import use_bootstrap3, use_select2
from corehq.apps.style.forms.widgets import DateRangePickerWidget
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import Permissions
from corehq.util.timezones.utils import get_timezone_for_user
import couchexport
from couchexport.models import SavedExportSchema, ExportSchema
from couchexport.schema import build_latest_schema
from couchexport.util import SerializableFunction
from couchforms.filters import instances
from dimagi.utils.decorators.memoized import memoized
from django.utils.translation import ugettext as _, ugettext_noop, ugettext_lazy
from dimagi.utils.logging import notify_exception
from dimagi.utils.parsing import json_format_date
from dimagi.utils.web import json_response
from django_prbac.utils import has_privilege
from soil import DownloadBase
from soil.exceptions import TaskFailedError
from soil.util import get_download_context

require_form_export_permission = require_permission(
    Permissions.view_report,
    'corehq.apps.reports.standard.export.ExcelExportReport',
    login_decorator=None
)


class BaseExportView(BaseProjectDataView):
    template_name = 'export/customize_export.html'
    export_type = None
    is_async = True

    @property
    def parent_pages(self):
        return [{
            'title': self.report_class.name,
            'url': self.export_home_url,
        }]

    @method_decorator(require_form_export_permission)
    def dispatch(self, request, *args, **kwargs):
        return super(BaseExportView, self).dispatch(request, *args, **kwargs)

    @property
    def export_helper(self):
        raise NotImplementedError("You must implement export_helper!")

    def redirect_url(self, export_id):
        if self.request.body:
            preview = json.loads(self.request.body).get('preview')
            if preview:
                return reverse(
                    'export_custom_data',
                    args=[self.domain, export_id],
                ) + '?format=html&limit=50&type=%(type)s' % {
                    'type': self.export_type,
                }
        return self.export_home_url

    @property
    def export_home_url(self):
        return self.report_class.get_url(domain=self.domain)

    @property
    @memoized
    def report_class(self):
        try:
            return {
                'form': ExcelExportReport,
                'case': CaseExportReport
            }[self.export_type]
        except KeyError:
            raise SuspiciousOperation

    @property
    def page_context(self):
        return self.export_helper.get_context()

    def commit(self, request):
        raise NotImplementedError('Subclasses must implement a commit method.')

    def post(self, request, *args, **kwargs):
        try:
            export_id = self.commit(request)
        except Exception, e:
            if self.is_async:
                # todo: this can probably be removed as soon as
                # http://manage.dimagi.com/default.asp?157713 is resolved
                notify_exception(request, 'problem saving an export! {}'.format(str(e)))
                response = json_response({
                    'error': str(e) or type(e).__name__
                })
                response.status_code = 500
                return response
            elif isinstance(e, ExportAppException):
                return HttpResponseRedirect(request.META['HTTP_REFERER'])
            else:
                raise
        else:
            if self.is_async:
                return json_response({
                    'redirect': self.redirect_url(export_id),
                })
            return HttpResponseRedirect(self.redirect_url(export_id))


class BaseCreateCustomExportView(BaseExportView):
    # this view likely needs a lot more cleanup. will leave that for a later time...

    @property
    @memoized
    def export_helper(self):
        return make_custom_export_helper(self.request, self.export_type, domain=self.domain)

    def commit(self, request):
        export_id = self.export_helper.update_custom_export()
        messages.success(request, _("Custom export created!"))
        return export_id

    def get(self, request, *args, **kwargs):
        # just copying what was in the old django view here. don't want to mess too much with exports just yet.
        try:
            export_tag = [self.domain, json.loads(request.GET.get("export_tag", "null") or "null")]
        except ValueError:
            return HttpResponseBadRequest()

        if self.export_helper.export_type == "form" and not export_tag[1]:
            return HttpResponseRedirect(ExcelExportReport.get_url(domain=self.domain))

        schema = build_latest_schema(export_tag)

        if not schema and self.export_helper.export_type == "form":
            schema = create_basic_form_checkpoint(export_tag)

        if request.GET.get('minimal', False):
            # minimal mode is a HACK so that some large domains can load this page. halp.
            messages.warning(request,
                _("Warning you are using minimal mode, some things may not be functional"))

        if schema:
            app_id = request.GET.get('app_id')
            self.export_helper.custom_export = self.export_helper.ExportSchemaClass.default(
                schema=schema,
                name="%s: %s" % (
                    xmlns_to_name(self.domain, export_tag[1], app_id=app_id)
                        if self.export_helper.export_type == "form" else export_tag[1],
                    json_format_date(datetime.utcnow())
                ),
                type=self.export_helper.export_type
            )
            if self.export_helper.export_type in ['form', 'case']:
                self.export_helper.custom_export.app_id = app_id
            if self.export_helper.export_type == 'form':
                self.export_helper.custom_export.update_question_schema()

            return super(BaseCreateCustomExportView, self).get(request, *args, **kwargs)

        messages.warning(request, _("<strong>No data found for that form "
                                    "(%s).</strong> Submit some data before creating an export!") %
                         xmlns_to_name(self.domain, export_tag[1], app_id=None), extra_tags="html")
        return HttpResponseRedirect(ExcelExportReport.get_url(domain=self.domain))


class CreateCustomFormExportView(BaseCreateCustomExportView):
    urlname = 'custom_export_form'
    page_title = ugettext_lazy("Create Custom Form Export")
    export_type = 'form'


class CreateCustomCaseExportView(BaseCreateCustomExportView):
    urlname = 'custom_export_case'
    page_title = ugettext_lazy("Create Custom Case Export")
    export_type = 'case'


class BaseModifyCustomExportView(BaseExportView):

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain, self.export_id])

    @property
    def export_id(self):
        return self.kwargs.get('export_id')

    @property
    @memoized
    def export_helper(self):
        try:
            return make_custom_export_helper(self.request, self.export_type, self.domain, self.export_id)
        except ResourceNotFound:
            raise Http404()


class BaseEditCustomExportView(BaseModifyCustomExportView):

    def commit(self, request):
        export_id = self.export_helper.update_custom_export()
        messages.success(request, _("Custom export saved!"))
        return export_id


class EditCustomFormExportView(BaseEditCustomExportView):
    urlname = 'edit_custom_export_form'
    page_title = ugettext_noop("Edit Form Custom Export")
    export_type = 'form'


class EditCustomCaseExportView(BaseEditCustomExportView):
    urlname = 'edit_custom_export_case'
    page_title = ugettext_noop("Edit Case Custom Export")
    export_type = 'case'


class DeleteCustomExportView(BaseModifyCustomExportView):
    urlname = 'delete_custom_export'
    http_method_names = ['post']
    is_async = False

    def commit(self, request):
        try:
            saved_export = SavedExportSchema.get(self.export_id)
        except ResourceNotFound:
            raise ExportNotFound()
        self.export_type = saved_export.type
        saved_export.delete()
        touch_exports(self.domain)
        messages.success(request, _("Custom export was deleted."))


BASIC_FORM_SCHEMA = {
    "doc_type": "string",
    "domain": "string",
    "xmlns": "string",
    "form": {
        "@xmlns": "string",
        "@uiVersion": "string",
        "@name": "string",
        "#type": "string",
        "meta": {
            "@xmlns": "string",
            "username": "string",
            "instanceID": "string",
            "userID": "string",
            "timeEnd": "string",
            "appVersion": {
                "@xmlns": "string",
                "#text": "string"
            },
            "timeStart": "string",
            "deviceID": "string"
        },
        "@version": "string"
    },
    "partial_submission": "string",
    "_rev": "string",
    "#export_tag": [
       "string"
    ],
    "received_on": "string",
    "app_id": "string",
    "last_sync_token": "string",
    "submit_ip": "string",
    "computed_": {
    },
    "openrosa_headers": {
       "HTTP_DATE": "string",
       "HTTP_ACCEPT_LANGUAGE": "string",
       "HTTP_X_OPENROSA_VERSION": "string"
    },
    "date_header": "string",
    "path": "string",
    "computed_modified_on_": "string",
    "_id": "string"
}


def create_basic_form_checkpoint(index):
    checkpoint = ExportSchema(
        schema=BASIC_FORM_SCHEMA,
        timestamp=datetime(1970, 1, 1),
        index=index,
    )
    checkpoint.save()
    return checkpoint


class BaseDownloadExportView(JSONResponseMixin, BaseProjectDataView):
    template_name = 'export/download_export.html'

    @method_decorator(use_bootstrap3())
    @method_decorator(use_select2())
    def dispatch(self, *args, **kwargs):
        return super(BaseDownloadExportView, self).dispatch(*args, **kwargs)

    @property
    @memoized
    def timezone(self):
        if not self.domain:
            return pytz.utc
        else:
            try:
                return get_timezone_for_user(self.request.couch_user, self.domain)
            except AttributeError:
                return get_timezone_for_user(None, self.domain)

    @property
    @memoized
    def default_datespan(self):
        return datespan_from_beginning(self.domain, 7, self.timezone)

    @property
    def page_context(self):
        return {
            'download_export_form': self.download_export_form,
            'export_list': self.export_list,
            'max_column_size': self.max_column_size,
            'default_date_range': '%(startdate)s%(separator)s%(enddate)s' % {
                'startdate': self.default_datespan.startdate.strftime('%Y-%m-%d'),
                'enddate': self.default_datespan.enddate.strftime('%Y-%m-%d'),
                'separator': DateRangePickerWidget.separator,
            }
        }

    @property
    def download_export_form(self):
        """Should return a memoized instance that is a subclass of
        FilterExportDownloadForm.
        """
        raise NotImplementedError("You must implement download_export_form.")

    @property
    @memoized
    def export(self):
        return SavedExportSchema.get(self.export_id)

    @property
    def export_id(self):
        return self.kwargs.get('export_id')

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain, self.export_id])

    @property
    def export_list(self):
        return [self.download_export_form.format_export_data(self.export)]

    @property
    def max_column_size(self):
        try:
            return int(self.request.GET.get('max_column_size', 2000))
        except TypeError:
            return 2000

    @property
    def can_view_deid(self):
        return has_privilege(self.request, privileges.DEIDENTIFIED_DATA)

    def get_filters(self, filter_form_data):
        """Should return a SerializableFunction object to be passed to the
        exports framework for filtering the final download.
        """
        raise NotImplementedError(
            "Must return a SerializableFunction for get_filters."
        )

    def get_export_object(self, export_id):
        """Must return either a FormExportSchema or CaseExportSchema object
        """
        raise NotImplementedError(
            "Must implement get_export_object."
        )

    @allow_remote_invocation
    def get_group_options(self, in_data):
        groups = map(
            lambda g: {'id': g._id, 'text': g.name},
            Group.get_reporting_groups(self.domain)
        )
        return {
            'success': True,
            'groups': groups,
        }

    @allow_remote_invocation
    def poll_custom_export_download(self, in_data):
        try:
            download_id = in_data['download_id']
        except KeyError:
            return {
                'error': _("Requires a download id")
            }
        try:
            context = get_download_context(download_id, check_state=True)
        except TaskFailedError as e:
            print e
            context = {'error': list(e)}
        if context.get('is_ready', False):
            context.update({
                'dropbox_url': reverse('dropbox_upload', args=(download_id,)),
                'download_url': "{}?get_file".format(
                    reverse('retrieve_download', args=(download_id,))
                ),
            })
        context['is_poll_successful'] = True
        return context

    @allow_remote_invocation
    def prepare_custom_export(self, in_data):
        """Uses the current exports download framework (with some nasty filters)
        to return the current download id to POLL for the download status.
        A successful request returns:
        {
            'success': True,
            'download_id': '<some uuid>',
        }
        """
        # todo
        # - eventually combine users + group field, but to do that exports
        #   might need a revamp, so leaving that for later.
        try:
            exports = in_data['exports']
            filter_form_data = in_data['form_data']
        except (KeyError, TypeError):
            return {
                'error': ("Request requires a list of exports and filters."),
            }

        if filter_form_data['type_or_group'] != 'group':
            # make double sure that group is none
            filter_form_data['group'] = ''

        try:
            export_filter = self.get_filters(filter_form_data)
        except ExportFormValidationException:
            return {
                'error': _("Form did not validate."),
            }

        export_data = exports[0]
        export_object = self.get_export_object(export_data['export_id'])
        export_object.update_schema()

        # if the export is de-identified (is_safe), check that
        # the requesting domain has access to the deid feature.
        if export_object.is_safe and not self.can_view_deid:
            return {
                'error': _(
                    "You do not have permission to download de-identified "
                    "exports."
                )
            }

        max_column_size = int(in_data.get('max_column_size', 2000))

        filename = export_data.get('filename', export_object.name)
        filename += ' ' + date.today().isoformat()

        download = DownloadBase()
        download.set_task(couchexport.tasks.export_async.delay(
            export_object,
            download.download_id,
            format=export_object.default_format,
            filter=export_filter,
            filename=filename,
            previous_export_id=None,
            max_column_size=max_column_size,
        ))
        return {
            'success': True,
            'download_id': download.download_id,
        }


class DownloadFormExportView(BaseDownloadExportView):
    """View to download a SINGLE Form Export with filters.
    """
    urlname = 'export_download_forms'
    page_title = ugettext_noop("Download Form Export")

    @property
    @memoized
    def download_export_form(self):
        return FilterFormExportDownloadForm(
            self.domain,
            self.timezone,
            initial={
                'type_or_group': 'type',
            },
        )

    @property
    def parent_pages(self):
        return [{
            'title': _("Export Forms"),
            'url': '#',
        }]

    def get_filters(self, filter_form_data):
        filter_form = FilterFormExportDownloadForm(
            self.domain, self.timezone, filter_form_data)
        if not filter_form.is_valid():
            raise ExportFormValidationException()
        form_filter = filter_form.get_form_filter()
        export_filter = SerializableFunction(default_form_filter,
                                             filter=form_filter)
        return export_filter

    def get_export_object(self, export_id):
        return FormExportSchema.get(export_id)


class DownloadCaseExportView(BaseDownloadExportView):
    """View to download a SINGLE Case Export with Filters
    """
    urlname = 'export_download_cases'
    page_title = ugettext_noop("Download Case Export")

    @property
    @memoized
    def download_export_form(self):
        return FilterCaseExportDownloadForm(
            self.domain,
            self.timezone,
            initial={
                'type_or_group': 'type',
            },
        )

    @property
    def parent_pages(self):
        return [{
            'title': _("Export Cases"),
            'url': '#',
        }]

    def get_filters(self, filter_form_data):
        filter_form = FilterCaseExportDownloadForm(
            self.domain, self.timezone, filter_form_data)
        if not filter_form.is_valid():
            raise ExportFormValidationException()
        return filter_form.get_case_filter()

    def get_export_object(self, export_id):
        return CaseExportSchema.get(export_id)


class BaseExportListView(JSONResponseMixin, BaseProjectDataView):
    template_name = 'export/export_list.html'

    @method_decorator(use_bootstrap3())
    @method_decorator(use_select2())
    def dispatch(self, *args, **kwargs):
        return super(BaseExportListView, self).dispatch(*args, **kwargs)

    @property
    def can_view_deid(self):
        return has_privilege(self.request, privileges.DEIDENTIFIED_DATA)

    @memoized
    def get_saved_exports(self):
        """Returns a list of saved exports
        """
        raise NotImplementedError("must implement get_saved_exports")

    @property
    @memoized
    def create_export_form(self):
        """Returns the create saved export form.
        """
        raise NotImplementedError("must implement create_export_form")

    @property
    def create_export_form_title(self):
        """Returns a string that is the title of the export form
        """
        raise NotImplementedError("must implement create_export_form_title")

    @property
    def page_context(self):
        return {
            'create_export_form': self.create_export_form,
            'create_export_form_title': self.create_export_form_title,
        }

    def fmt_export_data(self, export):
        """Return data for the export list table
        """
        raise NotImplementedError("must implement fmt_export_data")

    @allow_remote_invocation
    def get_exports_list(self, in_data):
        saved_exports = self.get_saved_exports()
        saved_exports = map(self.fmt_export_data, saved_exports)
        return {
            'success': True,
            'exports': saved_exports,
        }

    @allow_remote_invocation
    def get_initial_form_data(self, in_data):
        """Returns data needed to initialize the Create Export Form
        """
        raise NotImplementedError("Must implement get_intial_form_data")

    def get_create_export_url(self, form_data):
        """Returns url to custom export creation form.
        """
        raise NotImplementedError("Must implement generate_create_form_url")

    @allow_remote_invocation
    def process_create_form(self, in_data):
        try:
            form_data = in_data['createFormData']
        except KeyError:
            return {
                'error': _("The form's data was not correctly formatted.")
            }
        try:
            create_url = self.get_create_export_url(form_data)
        except ExportFormValidationException:
            return {
                'error': _("The form did not validate.")
            }
        except Exception as e:
            return {
                'error': _("Problem getting link to custom export form: %s") % e.message,
            }
        return {
            'success': True,
            'url': create_url,
        }


class FormExportListView(BaseExportListView):
    urlname = 'list_form_exports'
    page_title = ugettext_noop("Form Exports")

    @memoized
    def get_saved_exports(self):
        exports = FormExportSchema.get_stale_exports(self.domain)
        if not self.can_view_deid:
            exports = filter(lambda x: not x.is_safe, exports)
        return sorted(exports, key=lambda x: x.name)

    @property
    @memoized
    def create_export_form(self):
        return CreateFormExportForm()

    @property
    def create_export_form_title(self):
        return _("Select a Form to Export")

    def fmt_export_data(self, export):
        return {
            'id': export.get_id,
            'isDeid': export.is_safe,
            'name': export.name,
            'formname': export.formname,
            'addedToBulk': False,
            'editUrl': reverse(EditCustomFormExportView.urlname,
                               args=(self.domain, export.get_id)),
            'downloadUrl': reverse(DownloadFormExportView.urlname,
                                   args=(self.domain, export.get_id)),
        }

    @allow_remote_invocation
    def get_initial_form_data(self, in_data):
        try:
            apps = get_apps_in_domain(self.domain)
            app_choices = map(
                lambda a: {'id': a._id, 'text': a.name},
                apps
            )
            modules = {}
            forms = {}

            def _fmt_name(n):
                if isinstance(n, dict):
                    return n.get(default_lang, _("Untitled"))
                if isinstance(n, basestring):
                    return n
                return _("Untitled")

            for app in apps:
                default_lang = app.default_language
                modules[app._id] = map(
                    lambda m: {
                        'id': m.unique_id,
                        'text': _fmt_name(m.name),
                    },
                    app.modules
                )
                forms[app._id] = map(
                    lambda f: {
                        'id': f['form'].get_unique_id(),
                        'text': _fmt_name(f['form'].name),
                        'module': f.get('module_unique_id', '_registration'),
                    },
                    app.get_forms(bare=False)
                )
        except Exception as e:
            return {
                'error': _("Problem getting Create Export Form: %s") % e.message,
            }
        return {
            'success': True,
            'apps': app_choices,
            'modules': modules,
            'forms': forms,
            'placeholders': {
                'application': _("Select Application"),
                'module': _("Select Module"),
                'form': _("Select Form"),
            }
        }

    def get_create_export_url(self, form_data):
        create_form = CreateFormExportForm(form_data)
        if not create_form.is_valid():
            raise ExportFormValidationException()

        app_id = create_form.cleaned_data['application']
        form_unique_id = create_form.cleaned_data['form']
        return reverse(
            CreateCustomFormExportView.urlname,
            args=[self.domain],
        ) + ('?export_tag="%(export_tag)s"&app_id=%(app_id)s' % {
            'app_id': app_id,
            'export_tag': [
                form for form in Application.get(app_id).get_forms()
                if form.get_unique_id() == form_unique_id
            ][0].xmlns,
        })


class CaseExportListView(BaseExportListView):
    urlname = 'list_case_exports'
    page_title = ugettext_noop("Case Exports")

    @memoized
    def get_saved_exports(self):
        exports = CaseExportSchema.get_stale_exports(self.domain)
        if not self.can_view_deid:
            exports = filter(lambda x: not x.is_safe, exports)
        return sorted(exports, key=lambda x: x.name)

    @property
    @memoized
    def create_export_form(self):
        return CreateCaseExportForm()

    @property
    def create_export_form_title(self):
        return _("Select a Case Type to Export")

    def fmt_export_data(self, export):
        return {
            'id': export.get_id,
            'isDeid': export.is_safe,
            'name': export.name,
            'addedToBulk': False,
            'editUrl': reverse(EditCustomCaseExportView.urlname,
                               args=(self.domain, export.get_id)),
            'downloadUrl': reverse(DownloadCaseExportView.urlname,
                                   args=(self.domain, export.get_id)),
        }

    @allow_remote_invocation
    def get_initial_form_data(self, in_data):
        try:
            apps = get_apps_in_domain(self.domain)
            app_choices = map(
                lambda a: {'id': a._id, 'text': a.name},
                apps
            )
            case_types = {}
            for app in apps:
                if hasattr(app, 'modules'):
                    case_types[app.get_id] = [
                        {'id': module.case_type, 'text': module.case_type}
                        for module in app.modules if module.case_type
                    ]
        except Exception as e:
            return {
                'error': _("Problem getting Create Export Form: %s") % e.message,
            }
        return {
            'success': True,
            'apps': app_choices,
            'case_types': case_types,
            'placeholders': {
                'application': _("Select Application"),
                'case_types': _("select Case Type"),
            },
        }

    def get_create_export_url(self, form_data):
        create_form = CreateCaseExportForm(form_data)
        if not create_form.is_valid():
            raise ExportFormValidationException()
        case_type = create_form.cleaned_data['case_type']
        return reverse(
            CreateCustomCaseExportView.urlname,
            args=[self.domain],
        ) + ('?export_tag="%(export_tag)s"' % {
            'export_tag': case_type,
        })
