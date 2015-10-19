from datetime import datetime, date
from couchdbkit import ResourceNotFound
from django.contrib import messages
from django.core.exceptions import SuspiciousOperation
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, HttpResponseBadRequest, Http404
from django.utils.decorators import method_decorator
import json
from django.utils.safestring import mark_safe

from djangular.views.mixins import JSONResponseMixin, allow_remote_invocation
import pytz
from corehq import toggles, privileges
from corehq.apps.app_manager.dbaccessors import get_apps_in_domain
from corehq.apps.app_manager.models import Application
from corehq.apps.app_manager.templatetags.xforms_extras import trans
from corehq.apps.export.custom_export_helpers import make_custom_export_helper
from corehq.apps.export.exceptions import (
    ExportNotFound,
    ExportAppException,
    ExportFormValidationException,
    ExportAsyncException,
)
from corehq.apps.export.forms import (
    CreateFormExportTagForm,
    CreateCaseExportTagForm,
    FilterFormExportDownloadForm,
    FilterCaseExportDownloadForm,
)
from corehq.apps.groups.models import Group
from corehq.apps.hqwebapp.templatetags.hq_shared_tags import toggle_enabled
from corehq.apps.reports.dbaccessors import touch_exports
from corehq.apps.reports.display import xmlns_to_name
from corehq.apps.reports.export import CustomBulkExportHelper
from corehq.apps.reports.exportfilters import default_form_filter
from corehq.apps.reports.models import FormExportSchema, CaseExportSchema
from corehq.apps.reports.standard.export import (
    CaseExportReport,
    ExcelExportReport,
)
from corehq.apps.reports.util import datespan_from_beginning
from corehq.apps.settings.views import BaseProjectDataView
from corehq.apps.style.decorators import (
    use_bootstrap3,
    use_select2,
    use_daterangepicker,
)
from corehq.apps.style.forms.widgets import DateRangePickerWidget
from corehq.apps.style.utils import format_angular_error, format_angular_success
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import Permissions
from corehq.util.timezones.utils import get_timezone_for_user
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
            'title': (self.report_class.page_title
                      if toggle_enabled(self.request, toggles.REVAMPED_EXPORTS)
                      else self.report_class.name),
            'url': self.export_home_url,
        }]

    @method_decorator(require_form_export_permission)
    def dispatch(self, request, *args, **kwargs):
        return super(BaseExportView, self).dispatch(request, *args, **kwargs)

    @property
    def export_helper(self):
        raise NotImplementedError("You must implement export_helper!")

    @property
    def export_home_url(self):
        if toggle_enabled(self.request, toggles.REVAMPED_EXPORTS):
            return reverse(self.report_class.urlname, args=(self.domain,))
        return self.report_class.get_url(domain=self.domain)

    @property
    @memoized
    def report_class(self):
        try:
            if toggle_enabled(self.request, toggles.REVAMPED_EXPORTS):
                base_views = {
                    'form': FormExportListView,
                    'case': CaseExportListView,
                }
            else:
                base_views = {
                    'form': ExcelExportReport,
                    'case': CaseExportReport,
                }
            return base_views[self.export_type]
        except KeyError:
            raise SuspiciousOperation

    @property
    def page_context(self):
        # It's really bad that the export_helper also handles a bunch of the view
        # interaction data. This should probably be rewritten as it's not exactly
        # clear what this view specifically needs to render.
        context = self.export_helper.get_context()
        context.update({'export_home_url': self.export_home_url})
        return context

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
                    'redirect': self.export_home_url,
                })
            return HttpResponseRedirect(self.export_home_url)


class BaseCreateCustomExportView(BaseExportView):
    """
    todo: Refactor in v2 of redesign
    """

    @property
    @memoized
    def export_helper(self):
        return make_custom_export_helper(
            self.request, self.export_type, domain=self.domain)

    def commit(self, request):
        export_id = self.export_helper.update_custom_export()
        messages.success(
            request,
            mark_safe(
                _("Export <strong>{}</strong> created.").format(
                    self.export_helper.custom_export.name
                )
            )
        )
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
            # minimal mode is a HACK so that some large domains can
            # load this page. halp.
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

        messages.warning(
            request, _(
                '<strong>No data found to export "%s".</strong> '
                'Please submit data before creating this export.'
            ) % xmlns_to_name(
                self.domain, export_tag[1], app_id=None), extra_tags="html")
        return HttpResponseRedirect(self.export_home_url)


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
        messages.success(
            request,
            mark_safe(
                _(
                    "Export <strong>%(export_name)s</strong> "
                    "was saved."
                ) % {'export_name': self.export_helper.custom_export.name}
            )
        )
        return export_id


class EditCustomFormExportView(BaseEditCustomExportView):
    urlname = 'edit_custom_export_form'
    page_title = ugettext_noop("Edit Form Export")
    export_type = 'form'


class EditCustomCaseExportView(BaseEditCustomExportView):
    urlname = 'edit_custom_export_case'
    page_title = ugettext_noop("Edit Case Export")
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
        messages.success(
            request,
            mark_safe(
                _("Export <strong>{}</strong> "
                  "was deleted.").format(saved_export.name)
            )
        )


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
    http_method_names = ['get', 'post']

    @use_daterangepicker
    @use_bootstrap3
    @use_select2
    def dispatch(self, *args, **kwargs):
        return super(BaseDownloadExportView, self).dispatch(*args, **kwargs)

    def post(self, request, *args, **kwargs):
        if not request.is_ajax():
            context = self.get_context_data(**kwargs)
            return self.render_to_response(context)
        return super(BaseDownloadExportView, self).post(request, *args, **kwargs)


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
        return datespan_from_beginning(self.domain, self.timezone)

    @property
    def page_context(self):
        context = {
            'download_export_form': self.download_export_form,
            'export_list': self.export_list,
            'export_list_url': self.export_list_url,
            'max_column_size': self.max_column_size,
            'allow_preview': bool(self.export_id),
        }
        if (
            self.default_datespan.startdate is not None
            and self.default_datespan.enddate is not None
        ):
            context.update({
                'default_date_range': '%(startdate)s%(separator)s%(enddate)s' % {
                    'startdate': self.default_datespan.startdate.strftime('%Y-%m-%d'),
                    'enddate': self.default_datespan.enddate.strftime('%Y-%m-%d'),
                    'separator': DateRangePickerWidget.separator,
                },
            })
        else:
            context.update({
                'default_date_range': _(
                    "You have no submissions in this project."
                ),
                'show_no_submissions_warning': True,
            })

        return context

    @property
    def export_list_url(self):
        """Should return a the URL for the export list view"""
        raise NotImplementedError("You must implement export_list_url")

    @property
    def download_export_form(self):
        """Should return a memoized instance that is a subclass of
        FilterExportDownloadForm.
        """
        raise NotImplementedError("You must implement download_export_form.")

    @staticmethod
    def get_export_schema(export_id):
        return SavedExportSchema.get(export_id)

    @property
    def export_id(self):
        return self.kwargs.get('export_id')

    @property
    def page_url(self):
        if self.export_id:
            return reverse(self.urlname, args=(self.domain, self.export_id))
        return reverse(self.urlname, args=(self.domain,))

    @property
    def export_list(self):
        exports = []
        if (
            self.request.method == 'POST'
            and 'export_list' in self.request.POST
            and not self.request.is_ajax()
        ):
            raw_export_list = json.loads(self.request.POST['export_list'])
            exports = map(lambda e: self.download_export_form.format_export_data(
                self.get_export_schema(e['id'])
            ), raw_export_list)
        elif self.export_id:
            exports = [self.download_export_form.format_export_data(
                self.get_export_schema(self.export_id))]
        return exports

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
        """Returns list of groups for the group filters
        :param in_data: dict passed by the  angular js controller.
        :return: {
            'success': True,
            'groups': [<..list of groups..>],
        }
        """
        groups = map(
            lambda g: {'id': g._id, 'text': g.name},
            Group.get_reporting_groups(self.domain)
        )
        return format_angular_success({
            'groups': groups,
        })

    @allow_remote_invocation
    def poll_custom_export_download(self, in_data):
        """Polls celery to see how the export download task is going.
        :param in_data: dict passed by the  angular js controller.
        :return: final response: {
            'success': True,
            'dropbox_url': '<url>',
            'download_url: '<url>',
            <task info>
        }
        """
        try:
            download_id = in_data['download_id']
        except KeyError:
            return format_angular_error(_("Requires a download id"))
        try:
            context = get_download_context(download_id, check_state=True)
        except TaskFailedError:
            return format_angular_error(
                _("Download Task Failed to Start. It seems that the server "
                  "might be under maintenance.")
            )
        if context.get('is_ready', False):
            context.update({
                'dropbox_url': reverse('dropbox_upload', args=(download_id,)),
                'download_url': "{}?get_file".format(
                    reverse('retrieve_download', args=(download_id,))
                ),
            })
        context['is_poll_successful'] = True
        return context

    def _get_bulk_download_task(self, export_specs, export_filter):
        export_helper = CustomBulkExportHelper(domain=self.domain)
        return export_helper.get_download_task(export_specs, export_filter)

    def _get_download_task(self, export_specs, export_filter, max_column_size=2000):
        try:
            export_data = export_specs[0]
            export_object = self.get_export_object(export_data['export_id'])
        except (KeyError, IndexError):
            raise ExportAsyncException(
                _("You need to pass a list of at least one export schema.")
            )
        export_object.update_schema()

        # if the export is de-identified (is_safe), check that
        # the requesting domain has access to the deid feature.
        if export_object.is_safe and not self.can_view_deid:
            raise ExportAsyncException(
                _("You do not have permission to export this "
                  "De-Identified export.")
            )

        return export_object.get_download_task(
            filter=export_filter,
            filename="{}{}".format(export_object.name,
                                   date.today().isoformat()),
            previous_export_id=None,
            max_column_size=max_column_size,
        )

    def _process_filters_and_specs(self, in_data):
        """Returns a the export filters and a list of JSON export specs
        """
        try:
            export_specs = in_data['exports']
            filter_form_data = in_data['form_data']
        except (KeyError, TypeError):
            raise ExportAsyncException(
                _("Request requires a list of exports and filters.")
            )

        if filter_form_data['type_or_group'] != 'group':
            # make double sure that group is none
            filter_form_data['group'] = ''

        try:
            export_filter = self.get_filters(filter_form_data)
        except ExportFormValidationException:
            raise ExportAsyncException(
                _("Form did not validate.")
            )

        return export_filter, export_specs

    @allow_remote_invocation
    def prepare_custom_export(self, in_data):
        """Uses the current exports download framework (with some nasty filters)
        to return the current download id to POLL for the download status.
        :param in_data: dict passed by the  angular js controller.
        :return: {
            'success': True,
            'download_id': '<some uuid>',
        }
        """
        try:
            export_filter, export_specs = self._process_filters_and_specs(in_data)
            if len(export_specs) > 1:
                download = self._get_bulk_download_task(export_specs, export_filter)
            else:
                max_column_size = int(in_data.get('max_column_size', 2000))
                download = self._get_download_task(
                    export_specs, export_filter, max_column_size
                )
        except ExportAsyncException as e:
            return format_angular_error(e.message)
        except Exception as e:
            return format_angular_error(
                e.message,
                log_error=True,
                exception=e,
                request=self.request,
            )
        return format_angular_success({
            'download_id': download.download_id,
        })

    @allow_remote_invocation
    def get_preview(self, in_data):
        """Returns the preview data for an export (currently does NOT support
        bulk export.
        :param in_data: dict passed by the  angular js controller.
        :return: {
            'success': True,
            'preview_data': [
                {
                    'table_name': '<table_name>',
                    'headers': ['<header1>', ...].
                    'rows': [
                        ['<col1>',...],
                    ],
                },
            ],
        }
        """
        try:
            export_filter, export_specs = self._process_filters_and_specs(in_data)
            export = export_specs[0]
            export_object = self.get_export_schema(export['export_id'])
            preview_data = export_object.get_preview_data(export_filter)
        except ExportAsyncException as e:
            return format_angular_error(e.message)
        except Exception as e:
            return format_angular_error(
                _("Issue processing preview of export: %s") % e.message,
                log_error=True,
                exception=e,
                request=self.request,
            )
        return format_angular_success({
            'preview_data': preview_data,
        })


class DownloadFormExportView(BaseDownloadExportView):
    """View to download a SINGLE Form Export with filters.
    """
    urlname = 'export_download_forms'
    page_title = ugettext_noop("Download Form Export")

    @staticmethod
    def get_export_schema(export_id):
        return FormExportSchema.get(export_id)

    @property
    def export_list_url(self):
        return reverse(FormExportListView.urlname, args=(self.domain,))

    @property
    @memoized
    def download_export_form(self):
        return FilterFormExportDownloadForm(
            self.domain_object,
            self.timezone,
            initial={
                'type_or_group': 'type',
            },
        )

    @property
    def parent_pages(self):
        return [{
            'title': FormExportListView.page_title,
            'url': reverse(FormExportListView.urlname, args=(self.domain,)),
        }]

    def get_filters(self, filter_form_data):
        filter_form = FilterFormExportDownloadForm(
            self.domain_object, self.timezone, filter_form_data)
        if not filter_form.is_valid():
            raise ExportFormValidationException()
        form_filter = filter_form.get_form_filter()
        export_filter = SerializableFunction(default_form_filter,
                                             filter=form_filter)
        return export_filter

    def get_export_object(self, export_id):
        return FormExportSchema.get(export_id)


class BulkDownloadFormExportView(DownloadFormExportView):
    """View to download a Bulk Form Export with filters.
    """
    urlname = 'export_bulk_download_forms'
    page_title = ugettext_noop("Download Form Exports")

    def get_filters(self, filter_form_data):
        filters = super(BulkDownloadFormExportView, self).get_filters(filter_form_data)
        filters &= SerializableFunction(instances)
        return filters


class DownloadCaseExportView(BaseDownloadExportView):
    """View to download a SINGLE Case Export with Filters
    """
    urlname = 'export_download_cases'
    page_title = ugettext_noop("Download Case Export")

    @staticmethod
    def get_export_schema(export_id):
        return CaseExportSchema.get(export_id)

    @property
    def export_list_url(self):
        return reverse(CaseExportListView.urlname, args=(self.domain,))

    @property
    @memoized
    def download_export_form(self):
        return FilterCaseExportDownloadForm(
            self.domain_object,
            self.timezone,
            initial={
                'type_or_group': 'type',
            },
        )

    @property
    def parent_pages(self):
        return [{
            'title': CaseExportListView.page_title,
            'url': reverse(CaseExportListView.urlname, args=(self.domain,)),
        }]

    def get_filters(self, filter_form_data):
        filter_form = FilterCaseExportDownloadForm(
            self.domain_object, self.timezone, filter_form_data)
        if not filter_form.is_valid():
            raise ExportFormValidationException()
        return filter_form.get_case_filter()

    def get_export_object(self, export_id):
        return CaseExportSchema.get(export_id)


class BulkDownloadCaseExportView(DownloadCaseExportView):
    """View to download a Bulk Case Export with filters.
    """
    urlname = 'bulk_download_cases'
    page_title = ugettext_noop("Download Case Exports")


class BaseExportListView(JSONResponseMixin, BaseProjectDataView):
    template_name = 'export/export_list.html'

    @use_bootstrap3
    @use_select2
    def dispatch(self, *args, **kwargs):
        return super(BaseExportListView, self).dispatch(*args, **kwargs)

    @property
    def page_context(self):
        return {
            'create_export_form': self.create_export_form,
            'create_export_form_title': self.create_export_form_title,
            'bulk_download_url': self.bulk_download_url,
        }

    @property
    def can_view_deid(self):
        return has_privilege(self.request, privileges.DEIDENTIFIED_DATA)

    @property
    def bulk_download_url(self):
        """Returns url for bulk download
        """
        raise NotImplementedError('must implement bulk_download_url')

    @memoized
    def get_saved_exports(self):
        """The source of the data that will be processed by fmt_export_data
        for use in the template.
        :return A list of saved exports that are lists of FormExportSchema
        or CaseExportSchema.
        """
        raise NotImplementedError("must implement get_saved_exports")

    def fmt_export_data(self, export):
        """Returns the object used for each row (per export)
        in the saved exports table. This data will eventually be processed as
        a JSON object by angular.js.
        :return dict
        """
        raise NotImplementedError("must implement fmt_export_data")

    @allow_remote_invocation
    def get_exports_list(self, in_data):
        """Called by the ANGULAR.JS controller ListExports controller in
        exports/list_exports.ng.js on initialization of that controller.
        :param in_data: dict passed by the  angular js controller.
        :return: {
            'success': True,
            'exports': map(self.fmt_export_data, self.get_saved_exports()),
        }
        """
        try:
            saved_exports = self.get_saved_exports()
            saved_exports = map(self.fmt_export_data, saved_exports)
        except Exception as e:
            return format_angular_error(
                _("Issue fetching list of exports: %s") % e.message,
                log_error=True,
                exception=e,
                request=self.request,
            )
        return format_angular_success({
            'exports': saved_exports,
        })

    @property
    def create_export_form_title(self):
        """Returns a string that is displayed as the title of the create
        export form below.
        """
        raise NotImplementedError("must implement create_export_title")

    @property
    @memoized
    def create_export_form(self):
        """Returns a django form that gets the information necessary to create
        an export tag, which is the first step in creating a new export.

        This is either an instance of:
        - CreateFormExportTagForm
        - CreateCaseExportTagForm

        This form is what will interact with the CreateExportController in
        exports/list_exports.ng.js
        """
        raise NotImplementedError("must implement create_export_form")

    @allow_remote_invocation
    def get_initial_create_form_data(self, in_data):
        """Called by the ANGULAR.JS controller CreateExportController in
        exports/list_exports.ng.js.
        :param in_data: dict passed by the  angular js controller.
        :return: {
            'success': True,
            'apps': [{'id': '<app_id>', 'text': '<app_name>'}, ...],
            the rest is dependent on form requirements, but as an example:
                'modules': {
                    '<app_id>': [{'id': '<module_id>', 'text': '<module_name>'}],
                },
                'placeholders': {
                  'applications': "Select Application",
                }
            }

        Notes:
        ----
        This returned dict also provides additional selection information for
        modules, forms, and case_types depending on what application is selected
        and which form is being used.

        This dict also returns placeholder info for the select2 widgets.
        """
        NotImplementedError("Must implement get_intial_form_data")

    def get_create_export_url(self, form_data):
        """Returns url to the custom export creation form with the export
        tag appended.
        """
        raise NotImplementedError("Must implement generate_create_form_url")

    @allow_remote_invocation
    def process_create_form(self, in_data):
        try:
            form_data = in_data['createFormData']
        except KeyError:
            return format_angular_error(
                _("The form's data was not correctly formatted.")
            )
        try:
            create_url = self.get_create_export_url(form_data)
        except ExportFormValidationException:
            return format_angular_error(
                _("The form did not validate.")
            )
        except Exception as e:
            return format_angular_error(
                _("Problem getting link to custom export form: %s") % e.message,
            )
        return format_angular_success({
            'url': create_url,
        })


class FormExportListView(BaseExportListView):
    urlname = 'list_form_exports'
    page_title = ugettext_noop("Export Forms")

    @property
    def bulk_download_url(self):
        return reverse(BulkDownloadFormExportView.urlname, args=(self.domain,))

    @memoized
    def get_saved_exports(self):
        exports = FormExportSchema.get_stale_exports(self.domain)
        if not self.can_view_deid:
            exports = filter(lambda x: not x.is_safe, exports)
        return sorted(exports, key=lambda x: x.name)

    @property
    @memoized
    def create_export_form(self):
        return CreateFormExportTagForm()

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
    def get_initial_create_form_data(self, in_data):
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
                        'module': (
                            f['module'].unique_id if 'module' in f
                            else '_registration'
                        ),
                    },
                    app.get_forms(bare=False)
                )
        except Exception as e:
            return format_angular_error(
                _("Problem getting Create Export Form: %s") % e.message,
            )
        return format_angular_success({
            'apps': app_choices,
            'modules': modules,
            'forms': forms,
            'placeholders': {
                'application': _("Select Application"),
                'module': _("Select Module"),
                'form': _("Select Form"),
            }
        })

    def get_create_export_url(self, form_data):
        create_form = CreateFormExportTagForm(form_data)
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
    page_title = ugettext_noop("Export Cases")

    @property
    def bulk_download_url(self):
        return reverse(BulkDownloadCaseExportView.urlname, args=(self.domain,))

    @memoized
    def get_saved_exports(self):
        exports = CaseExportSchema.get_stale_exports(self.domain)
        if not self.can_view_deid:
            exports = filter(lambda x: not x.is_safe, exports)
        return sorted(exports, key=lambda x: x.name)

    @property
    @memoized
    def create_export_form(self):
        return CreateCaseExportTagForm()

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
    def get_initial_create_form_data(self, in_data):
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
            return format_angular_error(
                _("Problem getting Create Export Form: %s") % e.message,
                log_error=True,
                exception=e,
                request=self.request,
            )
        return format_angular_success({
            'apps': app_choices,
            'case_types': case_types,
            'placeholders': {
                'application': _("Select Application"),
                'case_types': _("select Case Type"),
            },
        })

    def get_create_export_url(self, form_data):
        create_form = CreateCaseExportTagForm(form_data)
        if not create_form.is_valid():
            raise ExportFormValidationException()
        case_type = create_form.cleaned_data['case_type']
        return reverse(
            CreateCustomCaseExportView.urlname,
            args=[self.domain],
        ) + ('?export_tag="%(export_tag)s"' % {
            'export_tag': case_type,
        })
