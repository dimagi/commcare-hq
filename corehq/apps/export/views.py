from __future__ import absolute_import

from __future__ import division
from __future__ import unicode_literals
from datetime import datetime, date, timedelta
from wsgiref.util import FileWrapper

from couchdbkit import ResourceNotFound
from django.conf import settings
from django.contrib import messages
from django.contrib.humanize.templatetags.humanize import naturaltime
from django.core.exceptions import SuspiciousOperation
from django.db.models import Sum
from django.urls import reverse
from django.http import HttpResponseRedirect, HttpResponseBadRequest, Http404, HttpResponse, \
    StreamingHttpResponse, HttpResponseServerError
from django.template.defaultfilters import filesizeformat
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from corehq.apps.analytics.tasks import send_hubspot_form, \
    HUBSPOT_CREATED_EXPORT_FORM_ID, HUBSPOT_DOWNLOADED_EXPORT_FORM_ID
from corehq.blobs.exceptions import NotFound
from corehq.toggles import MESSAGE_LOG_METADATA, PAGINATED_EXPORTS
from corehq.apps.export.export import get_export_download, get_export_size
from corehq.apps.export.models.new import DatePeriod, DailySavedExportNotification, DataFile, \
    EmailExportWhenDoneRequest
from corehq.apps.hqwebapp.views import HQJSONResponseMixin
from corehq.apps.hqwebapp.utils import format_angular_error, format_angular_success
from corehq.apps.locations.models import SQLLocation
from corehq.apps.locations.permissions import location_safe, location_restricted_response
from corehq.apps.reports.filters.case_list import CaseListFilter
from corehq.apps.reports.filters.users import ExpandedMobileWorkerFilter
from corehq.apps.reports.views import should_update_export, build_download_saved_export_response
from corehq.form_processor.utils import use_new_exports
from corehq.privileges import EXCEL_DASHBOARD, DAILY_SAVED_EXPORT
from django_prbac.utils import has_privilege
from django.utils.decorators import method_decorator
import json
import re
from django.utils.safestring import mark_safe
from django.views.generic import View

from djangular.views.mixins import allow_remote_invocation
import pytz
from corehq import privileges
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.app_manager.fields import ApplicationDataRMIHelper
from corehq.couchapps.dbaccessors import forms_have_multimedia
from corehq.apps.data_interfaces.dispatcher import require_can_edit_data
from corehq.apps.domain.decorators import login_and_domain_required, api_auth
from corehq.apps.export.utils import (
    convert_saved_export_to_export_instance,
    revert_new_exports,
)
from corehq.apps.export.custom_export_helpers import make_custom_export_helper
from corehq.apps.export.tasks import generate_schema_for_all_builds
from corehq.apps.export.exceptions import (
    ExportNotFound,
    ExportAppException,
    BadExportConfiguration,
    ExportFormValidationException,
    ExportAsyncException,
)
from corehq.apps.export.forms import (
    FilterFormCouchExportDownloadForm,
    FilterCaseCouchExportDownloadForm,
    EmwfFilterFormExport,
    FilterCaseESExportDownloadForm,
    FilterSmsESExportDownloadForm,
    CreateExportTagForm,
    DashboardFeedFilterForm,
)
from corehq.apps.export.models import (
    FormExportDataSchema,
    CaseExportDataSchema,
    SMSExportDataSchema,
    FormExportInstance,
    CaseExportInstance,
    SMSExportInstance,
    ExportInstance,
)
from corehq.apps.export.const import (
    FORM_EXPORT,
    CASE_EXPORT,
    MAX_EXPORTABLE_ROWS,
    MAX_DATA_FILE_SIZE,
    MAX_DATA_FILE_SIZE_TOTAL,
)
from corehq.apps.export.dbaccessors import (
    get_form_export_instances,
    get_case_export_instances,
    get_properly_wrapped_export_instance,
    get_case_exports_by_domain,
    get_form_exports_by_domain,
)
from corehq.apps.groups.models import Group
from corehq.apps.reports.dbaccessors import touch_exports, stale_get_export_count
from corehq.apps.reports.display import xmlns_to_name
from corehq.apps.reports.export import CustomBulkExportHelper
from corehq.apps.reports.exportfilters import default_form_filter
from corehq.apps.reports.models import FormExportSchema, CaseExportSchema, \
    HQGroupExportConfiguration
from corehq.apps.reports.util import datespan_from_beginning
from corehq.apps.reports.tasks import rebuild_export_task
from corehq.apps.settings.views import BaseProjectDataView
from corehq.apps.hqwebapp.decorators import (
    use_select2,
    use_daterangepicker,
    use_jquery_ui,
    use_ko_validation,
    use_angular_js)
from corehq.apps.hqwebapp.widgets import DateRangePickerWidget
from corehq.apps.users.decorators import get_permission_name
from corehq.apps.users.models import Permissions, CouchUser
from corehq.apps.users.permissions import FORM_EXPORT_PERMISSION, CASE_EXPORT_PERMISSION, \
    DEID_EXPORT_PERMISSION, has_permission_to_view_report
from corehq.apps.analytics.tasks import track_workflow
from corehq.util.couch import get_document_or_404_lite
from corehq.util.timezones.utils import get_timezone_for_user
from couchexport.models import SavedExportSchema, ExportSchema
from couchexport.schema import build_latest_schema
from couchexport.util import SerializableFunction
from couchforms.filters import instances
from memoized import memoized
from django.utils.translation import ugettext as _, ugettext_noop, ugettext_lazy
from dimagi.utils.logging import notify_exception
from dimagi.utils.parsing import json_format_date
from dimagi.utils.web import json_response, get_url_base
from dimagi.utils.couch import CriticalSection
from dimagi.utils.couch.undo import DELETED_SUFFIX
from soil import DownloadBase
from soil.exceptions import TaskFailedError
from soil.util import get_download_context, process_email_request
from soil.progress import get_task_status
from six.moves import map


def _get_timezone(domain, couch_user):
    if not domain:
        return pytz.utc
    else:
        try:
            return get_timezone_for_user(couch_user, domain)
        except AttributeError:
            return get_timezone_for_user(None, domain)


def user_can_view_deid_exports(domain, couch_user):
    return (domain_has_privilege(domain, privileges.DEIDENTIFIED_DATA)
            and couch_user.has_permission(
                domain,
                get_permission_name(Permissions.view_report),
                data=DEID_EXPORT_PERMISSION
            ))


class ExportsPermissionsMixin(object):
    """For mixing in with a subclass of BaseDomainView

    Users need to have edit permissions to create or update exports
    Users need the "view reports" permission to download exports
    The DEIDENTIFIED_DATA privilege is a pro-plan feature, and without it,
        users should not be able to create, update, or download deid exports.
    There are some users with access to a specific DeidExportReport.  If these
        users do not have the "view reports" permission, they should only be
        able to access deid reports.
    """
    @property
    def form_or_case(self):
        raise NotImplementedError("Does this view operate on forms or cases?")

    @property
    def has_edit_permissions(self):
        return self.request.couch_user.can_edit_data()

    @property
    def has_form_export_permissions(self):
        return has_permission_to_view_report(self.request.couch_user, self.domain, FORM_EXPORT_PERMISSION)

    @property
    def has_case_export_permissions(self):
        return has_permission_to_view_report(self.request.couch_user, self.domain, CASE_EXPORT_PERMISSION)

    @property
    def has_view_permissions(self):
        if self.form_or_case is None:
            return self.has_form_export_permissions or self.has_case_export_permissions
        elif self.form_or_case == "form":
            return self.has_form_export_permissions
        elif self.form_or_case == "case":
            return self.has_case_export_permissions
        return False

    @property
    def has_deid_view_permissions(self):
        # just a convenience wrapper around user_can_view_deid_exports
        return user_can_view_deid_exports(self.domain, self.request.couch_user)


class BaseExportView(BaseProjectDataView):
    template_name = 'export/customize_export_old.html'
    export_type = None
    is_async = True

    @use_jquery_ui
    def dispatch(self, *args, **kwargs):
        return super(BaseExportView, self).dispatch(*args, **kwargs)

    @property
    def parent_pages(self):
        return [{
            'title': self.report_class.page_title,
            'url': self.export_home_url,
        }]

    @property
    def export_helper(self):
        raise NotImplementedError("You must implement export_helper!")

    @property
    def export_home_url(self):
        return reverse(self.report_class.urlname, args=(self.domain,))

    @property
    @memoized
    def report_class(self):
        try:
            base_views = {
                'form': FormExportListView,
                'case': CaseExportListView,
            }
            return base_views[self.export_type]
        except KeyError:
            raise SuspiciousOperation('Attempted to access list view {}'.format(self.export_type))

    @property
    def page_context(self):
        # It's really bad that the export_helper also handles a bunch of the view
        # interaction data. This should probably be rewritten as it's not exactly
        # clear what this view specifically needs to render.
        context = self.export_helper.get_context()
        context.update({
            'export_home_url': self.export_home_url,
            'has_excel_dashboard_access': domain_has_privilege(self.domain, EXCEL_DASHBOARD),
            'has_daily_saved_export_access': domain_has_privilege(self.domain, DAILY_SAVED_EXPORT),
        })
        return context

    def commit(self, request):
        raise NotImplementedError('Subclasses must implement a commit method.')

    def post(self, request, *args, **kwargs):
        try:
            export_id = self.commit(request)
        except Exception as e:
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
            try:
                post_data = json.loads(self.request.body)
                url = self.export_home_url
                # short circuit to check if the submit is from a create or edit feed
                # to redirect it to the list view
                if isinstance(self, DashboardFeedMixin):
                    url = reverse(DashboardFeedListView.urlname, args=[self.domain])
                elif post_data['is_daily_saved_export']:
                    url = reverse(DailySavedExportListView.urlname, args=[self.domain])
            except ValueError:
                url = self.export_home_url
            if self.is_async:
                return json_response({
                    'redirect': url,
                })
            return HttpResponseRedirect(url)


class BaseCreateCustomExportView(BaseExportView):
    """
    todo: Refactor in v2 of redesign
    """

    @method_decorator(require_can_edit_data)
    def dispatch(self, request, *args, **kwargs):
        return super(BaseCreateCustomExportView, self).dispatch(request, *args, **kwargs)

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
        send_hubspot_form(HUBSPOT_CREATED_EXPORT_FORM_ID, request)
        return export_id

    def get(self, request, *args, **kwargs):
        # just copying what was in the old django view here. don't want to mess too much with exports just yet.
        try:
            export_tag = [self.domain, json.loads(request.GET.get("export_tag", "null") or "null")]
        except ValueError:
            return HttpResponseBadRequest()

        if self.export_helper.export_type == "form" and not export_tag[1]:
            return HttpResponseRedirect(reverse(FormExportListView.urlname, args=(self.domain,)))

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
    page_title = ugettext_lazy("Create Form Export")
    export_type = 'form'


class CreateCustomCaseExportView(BaseCreateCustomExportView):
    urlname = 'custom_export_case'
    page_title = ugettext_lazy("Create Case Export")
    export_type = 'case'


class BaseModifyCustomExportView(BaseExportView):

    @method_decorator(require_can_edit_data)
    def dispatch(self, request, *args, **kwargs):
        return super(BaseModifyCustomExportView, self).dispatch(request, *args, **kwargs)

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


class BaseDownloadExportView(ExportsPermissionsMixin, HQJSONResponseMixin, BaseProjectDataView):
    template_name = 'export/download_export.html'
    http_method_names = ['get', 'post']
    show_sync_to_dropbox = False  # remove when DBox issue is resolved.
    show_date_range = False
    check_for_multimedia = False
    filter_form_class = None
    sms_export = False

    @use_daterangepicker
    @use_select2
    @use_angular_js
    @method_decorator(login_and_domain_required)
    def dispatch(self, request, *args, **kwargs):
        if not (self.has_edit_permissions
                or self.has_view_permissions
                or self.has_deid_view_permissions):
            raise Http404()
        return super(BaseDownloadExportView, self).dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if not request.is_ajax():
            context = self.get_context_data(**kwargs)
            return self.render_to_response(context)
        return super(BaseDownloadExportView, self).post(request, *args, **kwargs)

    @property
    @memoized
    def timezone(self):
        return _get_timezone(self.domain, self.request.couch_user)

    @property
    @memoized
    def default_datespan(self):
        return datespan_from_beginning(self.domain_object, self.timezone)

    @property
    def page_context(self):
        context = {
            'download_export_form': self.download_export_form,
            'export_list': self.export_list,
            'export_list_url': self.export_list_url,
            'max_column_size': self.max_column_size,
            'show_sync_to_dropbox': self.show_sync_to_dropbox,
            'show_date_range': self.show_date_range,
            'check_for_multimedia': self.check_for_multimedia,
            'is_sms_export': self.sms_export,
        }
        if (
            self.default_datespan.startdate is not None
            and self.default_datespan.enddate is not None
        ):
            context.update({
                'default_date_range': '{startdate}{separator}{enddate}'.format(
                    startdate=self.default_datespan.startdate.strftime('%Y-%m-%d'),
                    enddate=self.default_datespan.enddate.strftime('%Y-%m-%d'),
                    separator=DateRangePickerWidget.separator,
                ),
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
    def get_export_schema(domain, export_id):
        doc = get_document_or_404_lite(SavedExportSchema, export_id)
        if doc.index[0] == domain:
            return doc
        raise Http404(_("Export not found"))

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
            exports = [self._get_export(self.domain, e['id']) for e in raw_export_list]
        elif self.export_id or self.sms_export:
            exports = [self._get_export(self.domain, self.export_id)]

        if not self.has_view_permissions:
            if self.has_deid_view_permissions:
                exports = [x for x in exports if x.is_safe]
            else:
                raise Http404()

        # if there are no exports, this page doesn't exist
        if not exports:
            raise Http404()

        exports = [self.download_export_form.format_export_data(e) for e in exports]
        return exports

    def _get_export(self, domain, export_id):
        return self.get_export_schema(self.domain, export_id)

    @property
    def max_column_size(self):
        try:
            return int(self.request.GET.get('max_column_size', 2000))
        except TypeError:
            return 2000

    def get_filters(self, filter_form_data):
        """Should return a SerializableFunction object to be passed to the
        exports framework for filtering the final download.
        """
        raise NotImplementedError(
            "Must return a SerializableFunction for get_filters."
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
        groups = [{'id': g._id, 'text': g.name} for g in Group.get_reporting_groups(self.domain)]
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
            return format_angular_error(_("Requires a download id"), log_error=False)
        try:
            context = get_download_context(download_id)
        except TaskFailedError:
            notify_exception(self.request, "Export download failed",
                             details={'download_id': download_id})
            return format_angular_error(
                _("Download Task Failed to Start. It seems that the server "
                  "might be under maintenance."),
                log_error=False,
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

    def _get_download_task(self, in_data):
        export_filter, export_specs = self._process_filters_and_specs(in_data)
        if len(export_specs) > 1:
            download = self._get_bulk_download_task(export_specs, export_filter)
        else:
            max_column_size = int(in_data.get('max_column_size', 2000))
            download = self._get_single_export_download_task(
                export_specs[0], export_filter, max_column_size
            )
        return download

    def _get_and_rebuild_export_schema(self, export_id):
        export_object = self.get_export_schema(self.domain, export_id)
        export_object.update_schema()
        return export_object

    def _get_bulk_download_task(self, export_specs, export_filter):
        for export_spec in export_specs:
            export_id = export_spec['export_id']
            self._get_and_rebuild_export_schema(export_id)
        export_helper = CustomBulkExportHelper(domain=self.domain)
        return export_helper.get_download_task(export_specs, export_filter)

    def _get_single_export_download_task(self, export_spec, export_filter, max_column_size=2000):
        export_id = export_spec['export_id']
        export_object = self._get_and_rebuild_export_schema(export_id)

        # if the export is de-identified (is_safe), check that
        # the requesting domain has access to the deid feature.
        if export_object.is_safe and not self.has_deid_view_permissions:
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

    @staticmethod
    def _get_form_data_and_specs(in_data):
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

        return filter_form_data, export_specs

    def _process_filters_and_specs(self, in_data):
        """Returns a the export filters and a list of JSON export specs
        """
        filter_form_data, export_specs = self._get_form_data_and_specs(in_data)
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
            download = self._get_download_task(in_data)
        except ExportAsyncException as e:
            return format_angular_error(e.message, log_error=True)
        except Exception:
            return format_angular_error(_("There was an error."), log_error=True)
        send_hubspot_form(HUBSPOT_DOWNLOADED_EXPORT_FORM_ID, self.request)
        return format_angular_success({
            'download_id': download.download_id,
        })


class DownloadFormExportView(BaseDownloadExportView):
    """View to download a SINGLE Form Export with filters.
    """
    urlname = 'export_download_forms'
    show_date_range = True
    page_title = ugettext_noop("Download Form Export")
    check_for_multimedia = True
    form_or_case = 'form'
    filter_form_class = FilterFormCouchExportDownloadForm

    @staticmethod
    def get_export_schema(domain, export_id):
        doc = get_document_or_404_lite(FormExportSchema, export_id)
        if doc.index[0] == domain:
            return doc
        raise Http404(_("Export not found"))

    @property
    def export_list_url(self):
        return reverse(FormExportListView.urlname, args=(self.domain,))

    @property
    @memoized
    def download_export_form(self):
        return self.filter_form_class(
            self.domain_object,
            self.timezone,
            initial={
                'type_or_group': 'type',
            },
        )

    @property
    def parent_pages(self):
        if not self.has_edit_permissions:
            return [{
                'title': DeIdFormExportListView.page_title,
                'url': reverse(DeIdFormExportListView.urlname, args=(self.domain,)),
            }]
        return [{
            'title': FormExportListView.page_title,
            'url': reverse(FormExportListView.urlname, args=(self.domain,)),
        }]

    def get_filters(self, filter_form_data):
        filter_form = self._get_filter_form(filter_form_data)
        form_filter = filter_form.get_form_filter()
        export_filter = SerializableFunction(default_form_filter,
                                             filter=form_filter)
        return export_filter

    @allow_remote_invocation
    def has_multimedia(self, in_data):
        """Checks to see if this form export has multimedia available to export
        """
        try:
            export_object = self._get_export(self.domain, self.export_id)
            if isinstance(export_object, ExportInstance):
                has_multimedia = export_object.has_multimedia
            else:
                has_multimedia = forms_have_multimedia(
                    self.domain,
                    export_object.app_id,
                    getattr(export_object, 'xmlns', '')
                )
        except Exception:
            return format_angular_error(_("There was an error"), log_error=True)
        return format_angular_success({
            'hasMultimedia': has_multimedia,
        })

    @allow_remote_invocation
    def prepare_form_multimedia(self, in_data):
        """Gets the download_id for the multimedia zip and sends it to the
        exportDownloadService in download_export.ng.js to begin polling for the
        zip file download.
        """
        try:
            filter_form_data, export_specs = self._get_form_data_and_specs(in_data)
            filter_form = self.filter_form_class(
                self.domain_object, self.timezone, filter_form_data
            )
            if not filter_form.is_valid():
                raise ExportFormValidationException(
                    _("Please check that you've submitted all required filters.")
                )
            download = DownloadBase()
            export_object = self._get_export(self.domain, export_specs[0]['export_id'])
            task_kwargs = self.get_multimedia_task_kwargs(in_data, filter_form, export_object,
                                                          download.download_id)
            from corehq.apps.reports.tasks import build_form_multimedia_zip
            download.set_task(build_form_multimedia_zip.delay(**task_kwargs))
        except Exception:
            return format_angular_error(_("There was an error"), log_error=True)
        return format_angular_success({
            'download_id': download.download_id,
        })

    def get_multimedia_task_kwargs(self, in_data, filter_form, export_object, download_id):
        return filter_form.get_multimedia_task_kwargs(export_object, download_id)

    def _get_filter_form(self, filter_form_data):
        filter_form = self.filter_form_class(
            self.domain_object, self.timezone, filter_form_data
        )
        if not filter_form.is_valid():
            raise ExportFormValidationException()
        return filter_form


class BulkDownloadFormExportView(DownloadFormExportView):
    """View to download a Bulk Form Export with filters.
    """
    urlname = 'export_bulk_download_forms'
    page_title = ugettext_noop("Download Form Exports")

    def get_filters(self, filter_form_data):
        filters = super(BulkDownloadFormExportView, self).get_filters(filter_form_data)
        filters &= SerializableFunction(instances)
        return filters

    @allow_remote_invocation
    def has_multimedia(self, in_data):
        return False


class DownloadCaseExportView(BaseDownloadExportView):
    """View to download a SINGLE Case Export with Filters
    """
    urlname = 'export_download_cases'
    page_title = ugettext_noop("Download Case Export")
    form_or_case = 'case'
    filter_form_class = FilterCaseCouchExportDownloadForm

    @staticmethod
    def get_export_schema(domain, export_id):
        doc = get_document_or_404_lite(CaseExportSchema, export_id)
        if doc.index[0] == domain:
            return doc
        raise Http404(_("Export not found"))

    @property
    def export_list_url(self):
        return reverse(CaseExportListView.urlname, args=(self.domain,))

    @property
    @memoized
    def download_export_form(self):
        return self.filter_form_class(
            self.domain_object,
            timezone=self.timezone,
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
        filter_form = self._get_filter_form(filter_form_data)
        return filter_form.get_case_filter()

    def _get_filter_form(self, filter_form_data):
        filter_form = self.filter_form_class(
            self.domain_object, self.timezone, filter_form_data,
        )
        if not filter_form.is_valid():
            raise ExportFormValidationException()
        return filter_form


class BaseExportListView(ExportsPermissionsMixin, HQJSONResponseMixin, BaseProjectDataView):
    template_name = 'export/export_list.html'
    allow_bulk_export = True
    is_deid = False

    @use_select2
    @use_angular_js
    @method_decorator(login_and_domain_required)
    def dispatch(self, request, *args, **kwargs):
        if not (self.has_edit_permissions or self.has_view_permissions
                or (self.is_deid and self.has_deid_view_permissions)):
            raise Http404()

        self.request = request

        if DailySavedExportNotification.user_to_be_notified(self.domain, self.request.couch_user):
            self.set_notify_new_daily_saved_export()

        return super(BaseExportListView, self).dispatch(self.request, *args, **kwargs)

    def set_notify_new_daily_saved_export(self):
        self.request.notify_new_daily_saved_export = True
        DailySavedExportNotification.mark_notified(self.request.couch_user.user_id, self.domain)

    @property
    def page_context(self):
        return {
            'create_export_form': self.create_export_form if not self.is_deid else None,
            'create_export_form_title': self.create_export_form_title if not self.is_deid else None,
            'legacy_bulk_download_url': self.legacy_bulk_download_url,
            'bulk_download_url': self.bulk_download_url,
            'allow_bulk_export': self.allow_bulk_export,
            'has_edit_permissions': self.has_edit_permissions,
            'is_deid': self.is_deid,
            "export_type_caps": _("Export"),
            "export_type": _("export"),
            "export_type_caps_plural": _("Exports"),
            "export_type_plural": _("exports"),
            "model_type": self.form_or_case,
            "static_model_type": True,
            'max_exportable_rows': MAX_EXPORTABLE_ROWS,
        }

    @property
    def legacy_bulk_download_url(self):
        """Returns url for legacy bulk download
        """
        if not self.allow_bulk_export:
            return None
        raise NotImplementedError('must implement legacy_bulk_download_url')

    @property
    def bulk_download_url(self):
        """Returns url for bulk download
        """
        if not self.allow_bulk_export:
            return None
        raise NotImplementedError('must implement bulk_download_url')

    @memoized
    def get_saved_exports(self):
        """The source of the data that will be processed by fmt_export_data
        for use in the template.
        :return A list of saved exports that are lists of FormExportSchema
        or CaseExportSchema.
        """
        raise NotImplementedError("must implement get_saved_exports")

    @property
    @memoized
    def emailed_export_groups(self):
        """The groups of saved exports by domain for daily emailed exports.
        """
        return HQGroupExportConfiguration.by_domain(self.domain)

    @property
    def daily_emailed_exports(self):
        """Returns a list of exports marked for a daily email.
        """
        raise NotImplementedError("must implement daily_emailed_exports")

    def fmt_export_data(self, export):
        """Returns the object used for each row (per export)
        in the saved exports table. This data will eventually be processed as
        a JSON object by angular.js.
        :return dict
        """
        raise NotImplementedError("must implement fmt_export_data")

    def fmt_emailed_export_data(self, group_id=None, index=None,
                                has_file=False, file_id=None, size=0,
                                last_updated=None, last_accessed=None,
                                download_url=None, filters=None, export_type=None):
        """
        Return a dictionary containing details about an emailed export.
        This will eventually be passed to an Angular controller.
        """
        file_data = {}
        if has_file:
            file_data = self._fmt_emailed_export_fileData(
                has_file, file_id, size, last_updated, last_accessed, download_url
            )

        location_restrictions = []
        locations = []
        if filters.accessible_location_ids:
            locations = SQLLocation.objects.filter(location_id__in=filters.accessible_location_ids)
        for location in locations:
            location_restrictions.append(location.display_name)

        return {
            'groupId': group_id,  # This can be removed when we're off legacy exports
            'hasFile': has_file,
            'index': index,  # This can be removed when we're off legacy exports
            'fileData': file_data,
            'filters': DashboardFeedFilterForm.get_form_data_from_export_instance_filters(
                filters, self.domain, export_type
            ),
            'isLocationSafeForUser': filters.is_location_safe_for_user(self.request),
            "locationRestrictions": location_restrictions,
        }

    def fmt_legacy_emailed_export_data(self, group_id=None, index=None,
                                has_file=False, saved_basic_export=None, is_safe=False):
        """
        Return a dictionary containing details about an emailed export.
        This will eventually be passed to an Angular controller.
        """
        file_data = {}
        if has_file:
            if is_safe:
                saved_download_url = 'hq_deid_download_saved_export'
            else:
                saved_download_url = 'hq_download_saved_export'

            file_data = self._fmt_emailed_export_fileData(
                has_file,
                saved_basic_export.get_id,
                saved_basic_export.size,
                saved_basic_export.last_updated,
                saved_basic_export.last_accessed,
                '{}?group_export_id={}'.format(
                    reverse(saved_download_url, args=[
                        self.domain, saved_basic_export.get_id
                    ]),
                    group_id
                )
            )

        return {
            'groupId': group_id,  # This can be removed when we're off legacy exports
            'hasFile': has_file,
            'index': index,  # This can be removed when we're off legacy exports
            'fileData': file_data,
            'isLocationSafeForUser': self.request.can_access_all_locations,
        }

    def _fmt_emailed_export_fileData(self, has_file, fileId, size, last_updated,
                                     last_accessed, download_url):
        """
        Return a dictionary containing details about an emailed export file.
        This will eventually be passed to an Angular controller.
        """
        if has_file:
            return {
                'fileId': fileId,
                'size': filesizeformat(size),
                'lastUpdated': naturaltime(last_updated),
                'showExpiredWarning': (
                    last_accessed and
                    last_accessed <
                    (datetime.utcnow() - timedelta(days=settings.SAVED_EXPORT_ACCESS_CUTOFF))
                ),
                'downloadUrl': download_url,
            }
        return {}

    def get_formatted_emailed_export(self, export):

        emailed_exports = [x for x in self.daily_emailed_exports if x.config.index[-1] == export.get_id]

        if not emailed_exports:
            return None
        assert len(emailed_exports) == 1
        emailed_export = emailed_exports[0]

        return self.fmt_legacy_emailed_export_data(
            group_id=emailed_export.group_id,
            index=emailed_export.config.index,
            has_file=emailed_export.saved_version is not None and emailed_export.saved_version.has_file(),
            saved_basic_export=emailed_export.saved_version,
            is_safe=export.is_safe,
        )

    def _get_daily_saved_export_metadata(self, export):

        return self.fmt_emailed_export_data(
            filters=export.filters,
            has_file=export.has_file(),
            file_id=export._id,
            size=export.file_size,
            last_updated=export.last_updated,
            last_accessed=export.last_accessed,
            download_url=self.request.build_absolute_uri(reverse(
                'download_daily_saved_export', args=[self.domain, export._id]
            )),
            export_type=type(export),
        )

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
            if self.is_deid:
                saved_exports = [x for x in saved_exports if x.is_safe]
            saved_exports = list(map(self.fmt_export_data, saved_exports))
        except Exception as e:
            return format_angular_error(
                _("Issue fetching list of exports: {}").format(e),
                log_error=True,
            )
        return format_angular_success({
            'exports': saved_exports,
        })

    @property
    def create_export_form_title(self):
        """Returns a string that is displayed as the title of the create
        export form below.
        """
        raise NotImplementedError("must implement create_export_form_title")

    @property
    def create_export_form(self):
        """Returns a django form that gets the information necessary to create
        an export tag, which is the first step in creating a new export.

        This form is what will interact with the DrilldownToFormController in
        hq.app_data_drilldown.ng.js
        """
        if self.has_case_export_permissions or self.has_form_export_permissions:
            return CreateExportTagForm(self.has_form_export_permissions, self.has_case_export_permissions)

    @allow_remote_invocation
    def get_app_data_drilldown_values(self, in_data):
        """Called by the ANGULAR.JS controller DrilldownToFormController in
        hq.app_data_drilldown.ng.js  Use ApplicationDataRMIHelper to help
        format the response.
        """
        raise NotImplementedError("Must implement get_intial_form_data")

    def get_create_export_url(self, form_data):
        """Returns url to the custom export creation form with the export
        tag appended.
        """
        raise NotImplementedError("Must implement generate_create_form_url")

    def update_emailed_es_export_data(self, in_data):
        from corehq.apps.export.tasks import rebuild_export_task
        export_instance_id = in_data['export']['id']
        rebuild_export_task.delay(export_instance_id)
        return format_angular_success({})

    @allow_remote_invocation
    def toggle_saved_export_enabled_state(self, in_data):
        if in_data['export']['isLegacy']:
            format_angular_error('Legacy export not supported', True)

        export_instance_id = in_data['export']['id']
        export_instance = get_properly_wrapped_export_instance(export_instance_id)
        export_instance.auto_rebuild_enabled = not in_data['export']['isAutoRebuildEnabled']
        export_instance.save()
        return format_angular_success({
            'isAutoRebuildEnabled': export_instance.auto_rebuild_enabled
        })

    @allow_remote_invocation
    def update_emailed_export_data(self, in_data):
        if not in_data['export']['isLegacy']:
            return self.update_emailed_es_export_data(in_data)

        group_id = in_data['component']['groupId']
        relevant_group = filter(lambda g: g.get_id, self.emailed_export_groups)[0]
        indexes = [x[0].index for x in relevant_group.all_exports]
        place_index = indexes.index(in_data['component']['index'])
        rebuild_export_task.delay(group_id, place_index)
        return format_angular_success({})

    @allow_remote_invocation
    def submit_app_data_drilldown_form(self, in_data):
        if self.is_deid:
            raise Http404()
        try:
            form_data = in_data['formData']
        except KeyError:
            return format_angular_error(
                _("The form's data was not correctly formatted."),
                log_error=False,
            )
        try:
            create_url = self.get_create_export_url(form_data)
        except ExportFormValidationException:
            return format_angular_error(
                _("The form did not validate."),
                log_error=False,
            )
        except Exception as e:
            return format_angular_error(
                _("Problem getting link to custom export form: {}").format(e),
                log_error=False,
            )
        return format_angular_success({
            'url': create_url,
        })


@location_safe
class DailySavedExportListView(BaseExportListView):
    urlname = 'list_daily_saved_exports'
    template_name = 'export/daily_saved_export_list.html'
    page_title = ugettext_lazy("Daily Saved Exports")
    form_or_case = None  # This view lists both case and form feeds
    allow_bulk_export = False

    def dispatch(self, *args, **kwargs):
        if not self._priv_check():
            raise Http404
        return super(DailySavedExportListView, self).dispatch(*args, **kwargs)

    def _priv_check(self):
        return domain_has_privilege(self.domain, DAILY_SAVED_EXPORT)

    def _get_create_export_class(self, model):
        return {
            "form": CreateNewDailySavedFormExport,
            "case": CreateNewDailySavedCaseExport,
        }[model]

    def _get_edit_export_class(self, model):
        return {
            "form": EditFormDailySavedExportView,
            "case": EditCaseDailySavedExportView
        }[model]

    @property
    def page_context(self):
        context = super(DailySavedExportListView, self).page_context
        model_type = None
        if self.has_form_export_permissions and not self.has_case_export_permissions:
            model_type = "form"
        if not self.has_form_export_permissions and self.has_case_export_permissions:
            model_type = "case"
        context.update({
            "model_type": model_type,
            "static_model_type": False,
            "export_filter_form": DashboardFeedFilterForm(
                self.domain_object,
                initial={
                    'type_or_group': 'type',
                },
            )
        })
        return context

    @property
    @memoized
    def create_export_form_title(self):
        return "Select a model to export"  # could be form or case

    @property
    def legacy_bulk_download_url(self):
        # Daily Saved exports do not support bulk download
        return ""

    @property
    def bulk_download_url(self):
        # Daily Saved exports do not support bulk download
        return ""

    @memoized
    def get_saved_exports(self):
        combined_exports = []
        if self.has_form_export_permissions:
            combined_exports.extend(get_form_exports_by_domain(self.domain, self.has_deid_view_permissions))
        if self.has_case_export_permissions:
            combined_exports.extend(get_case_exports_by_domain(self.domain, self.has_deid_view_permissions))
        combined_exports = sorted(combined_exports, key=lambda x: x.name)
        return [x for x in combined_exports if x.is_daily_saved_export and not x.export_format == "html"]

    @property
    def daily_emailed_exports(self):
        # This function only returns old-style exports. Since this view will only be visible for people using new
        # exports, it need not return anything.
        return []

    def fmt_export_data(self, export):
        if isinstance(export, FormExportInstance):
            edit_view = self._get_edit_export_class('form')
            download_view = DownloadNewFormExportView
            formname = export.formname
        else:
            edit_view = self._get_edit_export_class('case')
            download_view = DownloadNewCaseExportView
            formname = None

        emailed_export = self._get_daily_saved_export_metadata(export)

        return {
            'id': export.get_id,
            'isDeid': export.is_safe,
            'isLegacy': False,
            'name': export.name,
            'formname': formname,
            'addedToBulk': False,
            'exportType': export.type,
            'isDailySaved': True,
            'isAutoRebuildEnabled': export.auto_rebuild_enabled,
            'emailedExport': emailed_export,
            'editUrl': reverse(edit_view.urlname, args=(self.domain, export.get_id)),
            'downloadUrl': reverse(download_view.urlname, args=(self.domain, export.get_id)),
            'copyUrl': reverse(CopyExportView.urlname, args=(self.domain, export.get_id)),
        }

    @allow_remote_invocation
    def get_app_data_drilldown_values(self, in_data):
        if self.is_deid:
            raise Http404()
        try:
            rmi_helper = ApplicationDataRMIHelper(self.domain, self.request.couch_user)
            response = rmi_helper.get_dual_model_rmi_response()
        except Exception:
            return format_angular_error(
                _("Problem getting Create Daily Saved Export Form"),
                log_error=True,
            )
        return format_angular_success(response)

    def get_create_export_url(self, form_data):
        create_form = CreateExportTagForm(
            self.has_form_export_permissions,
            self.has_case_export_permissions,
            form_data
        )
        if not create_form.is_valid():
            raise ExportFormValidationException()

        if create_form.cleaned_data['model_type'] == "case":
            export_tag = create_form.cleaned_data['case_type']
            cls = self._get_create_export_class('case')
        else:
            export_tag = create_form.cleaned_data['form']
            cls = self._get_create_export_class('form')
        app_id = create_form.cleaned_data['application']
        app_id_param = '&app_id={}'.format(app_id) if app_id != ApplicationDataRMIHelper.UNKNOWN_SOURCE else ""

        return reverse(
            cls.urlname,
            args=[self.domain],
        ) + ('?export_tag="{export_tag}"{app_id_param}'.format(
            app_id_param=app_id_param,
            export_tag=export_tag,
        ))

    @allow_remote_invocation
    def commit_filters(self, in_data):
        if not self.has_edit_permissions:
            raise Http404

        export_id = in_data['export']['id']
        form_data = in_data['form_data']
        try:
            export = get_properly_wrapped_export_instance(export_id)

            if not export.filters.is_location_safe_for_user(self.request):
                return location_restricted_response(self.request)

            filter_form = DashboardFeedFilterForm(self.domain_object, form_data)
            if filter_form.is_valid():
                old_can_access_all_locations = export.filters.can_access_all_locations
                old_accessible_location_ids = export.filters.accessible_location_ids

                filters = filter_form.to_export_instance_filters(
                    # using existing location restrictions prevents a less restricted user from modifying
                    # restrictions on an export that a more restricted user created (which would mean the more
                    # restricted user would lose access to the export)
                    old_can_access_all_locations,
                    old_accessible_location_ids
                )
                if export.filters != filters:
                    export.filters = filters
                    export.save()
                    from corehq.apps.export.tasks import rebuild_export_task
                    rebuild_export_task.delay(export_id)
                return format_angular_success()
            else:
                return format_angular_error(
                    _("Problem saving dashboard feed filters: Invalid form"),
                    log_error=True)
        except Exception:
            return format_angular_error(_("Problem saving dashboard feed filters"),
                                        log_error=True)


@location_safe
class DashboardFeedListView(DailySavedExportListView):
    template_name = 'export/dashboard_feed_list.html'
    urlname = 'list_dashboard_feeds'
    page_title = ugettext_lazy("Excel Dashboard Integration")
    form_or_case = None  # This view lists both case and form feeds
    allow_bulk_export = False

    def _priv_check(self):
        return domain_has_privilege(self.domain, EXCEL_DASHBOARD)

    def _get_create_export_class(self, model):
        return {
            "form": CreateNewFormFeedView,
            "case": CreateNewCaseFeedView,
        }[model]

    def _get_edit_export_class(self, model):
        return {
            "form": EditFormFeedView,
            "case": EditCaseFeedView
        }[model]

    @property
    def page_context(self):
        context = super(DashboardFeedListView, self).page_context
        context.update({
            "export_type_caps": _("Dashboard Feed"),
            "export_type": _("dashboard feed"),
            "export_type_caps_plural": _("Dashboard Feeds"),
            "export_type_plural": _("dashboard feeds"),
        })
        return context

    def fmt_export_data(self, export):
        data = super(DashboardFeedListView, self).fmt_export_data(export)
        data.update({
            'isFeed': True,
        })
        return data

    @memoized
    def get_saved_exports(self):
        combined_exports = []
        if self.has_form_export_permissions:
            combined_exports.extend(get_form_exports_by_domain(self.domain, self.has_deid_view_permissions))
        if self.has_case_export_permissions:
            combined_exports.extend(get_case_exports_by_domain(self.domain, self.has_deid_view_permissions))
        combined_exports = sorted(combined_exports, key=lambda x: x.name)
        return [x for x in combined_exports if x.is_daily_saved_export and x.export_format == "html"]


@location_safe
class DataFileDownloadList(BaseProjectDataView):
    urlname = 'download_data_files'
    template_name = 'export/download_data_files.html'
    page_title = ugettext_lazy("Download Data Files")

    def get_context_data(self, **kwargs):
        context = super(DataFileDownloadList, self).get_context_data(**kwargs)
        context.update({
            'data_files': DataFile.objects.filter(domain=self.domain).order_by('filename').all(),
            'is_admin': self.request.couch_user.is_domain_admin(self.domain),
            'url_base': get_url_base(),
        })
        return context

    def post(self, request, *args, **kwargs):
        if request.FILES['file'].size > MAX_DATA_FILE_SIZE:
            messages.warning(
                request,
                _('The data file exceeds the maximum size of {} MB.').format(MAX_DATA_FILE_SIZE // (1024 * 1024))
            )
            return self.get(request, *args, **kwargs)

        aggregate = DataFile.objects.filter(domain=self.domain).aggregate(total_size=Sum('content_length'))
        if (
            aggregate['total_size'] and
            aggregate['total_size'] + request.FILES['file'].size > MAX_DATA_FILE_SIZE_TOTAL
        ):
            messages.warning(
                request,
                _('Uploading this data file would exceed the total allowance of {} GB for this project space. '
                  'Please remove some files in order to upload new files.').format(
                    MAX_DATA_FILE_SIZE_TOTAL // (1024 * 1024 * 1024))
            )
            return self.get(request, *args, **kwargs)

        data_file = DataFile()
        data_file.domain = self.domain
        data_file.filename = request.FILES['file'].name
        data_file.description = request.POST['description']
        data_file.content_type = request.FILES['file'].content_type
        data_file.content_length = request.FILES['file'].size
        data_file.save_blob(request.FILES['file'])
        messages.success(request, _('Data file "{}" uploaded'.format(data_file.description)))
        return HttpResponseRedirect(reverse(self.urlname, kwargs={'domain': self.domain}))


class DataFileDownloadDetail(BaseProjectDataView):
    urlname = 'download_data_file'

    def get(self, request, *args, **kwargs):
        try:
            data_file = DataFile.objects.filter(domain=self.domain).get(pk=kwargs['pk'])
            blob = data_file.get_blob()
            response = StreamingHttpResponse(FileWrapper(blob), content_type=data_file.content_type)
        except (DataFile.DoesNotExist, NotFound):
            raise Http404
        response['Content-Disposition'] = 'attachment; filename="' + data_file.filename + '"'
        response['Content-Length'] = data_file.content_length
        return response

    def delete(self, request, *args, **kwargs):
        try:
            data_file = DataFile.objects.filter(domain=self.domain).get(pk=kwargs['pk'])
        except DataFile.DoesNotExist:
            raise Http404
        data_file.delete()
        return HttpResponse(status=204)


class DailySavedExportPaywall(BaseProjectDataView):
    urlname = 'daily_saved_paywall'
    template_name = 'export/paywall.html'


class DashboardFeedPaywall(BaseProjectDataView):
    urlname = 'dashbaord_feeds_paywall'
    template_name = 'export/paywall.html'


def use_new_daily_saved_exports_ui(domain):
    """
    Return True if this domain should use the new daily saved exports UI
    The new daily saved exports UI puts Daily Saved Exports and Dashboard Feeds on their own pages.
    It also allows for the filtering of both of these types of exports.
    """
    def _has_no_old_exports(domain_):
        return not bool(stale_get_export_count(domain_))

    return use_new_exports(domain) and _has_no_old_exports(domain)


@location_safe
class FormExportListView(BaseExportListView):
    urlname = 'list_form_exports'
    page_title = ugettext_noop("Export Forms")
    form_or_case = 'form'

    @property
    def legacy_bulk_download_url(self):
        return reverse(BulkDownloadFormExportView.urlname, args=(self.domain,))

    @property
    def bulk_download_url(self):
        return reverse(BulkDownloadNewFormExportView.urlname, args=(self.domain,))

    @memoized
    def get_saved_exports(self):
        exports = get_form_exports_by_domain(self.domain, self.has_deid_view_permissions)
        if use_new_daily_saved_exports_ui(self.domain):
            # New exports display daily saved exports in their own view
            exports = [x for x in exports if not x.is_daily_saved_export]
        return exports

    @property
    @memoized
    def daily_emailed_exports(self):
        all_form_exports = []
        for group in self.emailed_export_groups:
            all_form_exports.extend(group.form_exports)
        return all_form_exports

    @property
    def create_export_form_title(self):
        return _("Select a Form to Export")

    def fmt_export_data(self, export):
        if use_new_exports(self.domain):
            edit_view = EditNewCustomFormExportView
        else:
            edit_view = EditCustomFormExportView

        if isinstance(export, FormExportSchema):
            emailed_export = self.get_formatted_emailed_export(export)
        else:
            # New export
            emailed_export = None
            if export.is_daily_saved_export:
                emailed_export = self._get_daily_saved_export_metadata(export)
        return {
            'id': export.get_id,
            'isLegacy': isinstance(export, FormExportSchema),
            'isDeid': export.is_safe,
            'name': export.name,
            'formname': export.formname,
            'addedToBulk': False,
            'exportType': export.type,
            'emailedExport': emailed_export,
            'editUrl': reverse(edit_view.urlname,
                               args=(self.domain, export.get_id)),
            'downloadUrl': self._get_download_url(export.get_id, isinstance(export, FormExportSchema)),
            'copyUrl': reverse(CopyExportView.urlname, args=(self.domain, export.get_id)),
        }

    def _get_download_url(self, export_id, is_legacy):
        if is_legacy:
            view_cls = DownloadFormExportView
        else:
            view_cls = DownloadNewFormExportView
        return reverse(view_cls.urlname, args=(self.domain, export_id))

    @allow_remote_invocation
    def get_app_data_drilldown_values(self, in_data):
        if self.is_deid:
            raise Http404()
        try:
            rmi_helper = ApplicationDataRMIHelper(self.domain, self.request.couch_user)
            response = rmi_helper.get_form_rmi_response()
        except Exception:
            return format_angular_error(
                _("Problem getting Create Export Form"),
                log_error=True,
            )
        return format_angular_success(response)

    def get_create_export_url(self, form_data):
        create_form = CreateExportTagForm(
            self.has_form_export_permissions,
            self.has_case_export_permissions,
            form_data
        )
        if not create_form.is_valid():
            raise ExportFormValidationException()

        app_id = create_form.cleaned_data['application']
        form_xmlns = create_form.cleaned_data['form']
        if use_new_exports(self.domain):
            cls = CreateNewCustomFormExportView
        else:
            cls = CreateCustomFormExportView
        return reverse(
            cls.urlname,
            args=[self.domain],
        ) + ('?export_tag="{export_tag}"{app_id}'.format(
            app_id=('&app_id={}'.format(app_id)
                    if app_id != ApplicationDataRMIHelper.UNKNOWN_SOURCE else ""),
            export_tag=form_xmlns,
        ))


class DeIdFormExportListView(FormExportListView):
    page_title = ugettext_noop("Export De-Identified Forms")
    urlname = 'list_form_deid_exports'
    is_deid = True

    @property
    def create_export_form(self):
        return None


class _DeidMixin(object):
    is_deid = True

    @property
    def create_export_form(self):
        return None

    def get_saved_exports(self):
        return [x for x in get_form_export_instances(self.domain) if x.is_safe]


@location_safe
class DeIdDailySavedExportListView(_DeidMixin, DailySavedExportListView):
    urlname = 'list_deid_daily_saved_exports'
    page_title = ugettext_noop("Export De-Identified Daily Saved Exports")

    def get_saved_exports(self):
        exports = super(DeIdDailySavedExportListView, self).get_saved_exports()
        return [x for x in exports if x.is_daily_saved_export and not x.export_format == "html"]


@location_safe
class DeIdDashboardFeedListView(_DeidMixin, DashboardFeedListView):
    urlname = 'list_deid_dashboard_feeds'
    page_title = ugettext_noop("Export De-Identified Dashboard Feeds")

    def get_saved_exports(self):
        exports = super(DeIdDashboardFeedListView, self).get_saved_exports()
        return [x for x in exports if x.is_daily_saved_export and x.export_format == "html"]


@location_safe
class CaseExportListView(BaseExportListView):
    urlname = 'list_case_exports'
    page_title = ugettext_noop("Export Cases")
    allow_bulk_export = False
    form_or_case = 'case'

    @property
    def page_name(self):
        if self.is_deid:
            return _("Export De-Identified Cases")
        return self.page_title

    @property
    @memoized
    def daily_emailed_exports(self):
        all_case_exports = []
        for group in self.emailed_export_groups:
            all_case_exports.extend(group.case_exports)
        return all_case_exports

    @memoized
    def get_saved_exports(self):
        exports = get_case_exports_by_domain(self.domain, self.has_deid_view_permissions)
        if use_new_daily_saved_exports_ui(self.domain):
            exports = [x for x in exports if not x.is_daily_saved_export]
        return exports

    @property
    def create_export_form_title(self):
        return _("Select a Case Type to Export")

    def fmt_export_data(self, export):
        if use_new_exports(self.domain):
            edit_view = EditNewCustomCaseExportView
        else:
            edit_view = EditCustomCaseExportView

        if isinstance(export, CaseExportSchema):
            emailed_export = self.get_formatted_emailed_export(export)
        else:
            # New export
            emailed_export = None
            if export.is_daily_saved_export:
                emailed_export = self._get_daily_saved_export_metadata(export)

        return {
            'id': export.get_id,
            'isDeid': export.is_safe,
            'isLegacy': isinstance(export, CaseExportSchema),
            'name': export.name,
            'addedToBulk': False,
            'exportType': export.type,
            'emailedExport': emailed_export,
            'editUrl': reverse(edit_view.urlname, args=(self.domain, export.get_id)),
            'downloadUrl': self._get_download_url(export._id, isinstance(export, CaseExportSchema)),
            'copyUrl': reverse(CopyExportView.urlname, args=(self.domain, export.get_id)),
        }

    def _get_download_url(self, export_id, is_legacy):
        if is_legacy:
            view_cls = DownloadCaseExportView
        else:
            view_cls = DownloadNewCaseExportView
        return reverse(view_cls.urlname, args=(self.domain, export_id))

    @allow_remote_invocation
    def get_app_data_drilldown_values(self, in_data):
        try:
            rmi_helper = ApplicationDataRMIHelper(self.domain, self.request.couch_user)
            response = rmi_helper.get_case_rmi_response()
        except Exception:
            return format_angular_error(
                _("Problem getting Create Export Form"),
                log_error=True,
            )
        return format_angular_success(response)

    def get_create_export_url(self, form_data):
        create_form = CreateExportTagForm(
            self.has_form_export_permissions,
            self.has_case_export_permissions,
            form_data
        )
        if not create_form.is_valid():
            raise ExportFormValidationException()
        case_type = create_form.cleaned_data['case_type']
        app_id = create_form.cleaned_data['application']
        if app_id == ApplicationDataRMIHelper.UNKNOWN_SOURCE:
            app_id_param = ''
        else:
            app_id_param = '&app_id={}'.format(app_id)

        if use_new_exports(self.domain):
            cls = CreateNewCustomCaseExportView
        else:
            cls = CreateCustomCaseExportView
        return reverse(
            cls.urlname,
            args=[self.domain],
        ) + ('?export_tag="{export_tag}"{app_id_param}'.format(
            export_tag=case_type,
            app_id_param=app_id_param,
        ))


class BaseNewExportView(BaseExportView):
    template_name = 'export/customize_export_new.html'

    @use_jquery_ui
    def dispatch(self, request, *args, **kwargs):
        return super(BaseNewExportView, self).dispatch(request, *args, **kwargs)

    @property
    def export_instance_cls(self):
        return {
            FORM_EXPORT: FormExportInstance,
            CASE_EXPORT: CaseExportInstance,
        }[self.export_type]

    @property
    def export_schema_cls(self):
        return {
            FORM_EXPORT: FormExportDataSchema,
            CASE_EXPORT: CaseExportDataSchema,
        }[self.export_type]

    @property
    def page_context(self):
        return {
            'export_instance': self.export_instance,
            'export_home_url': self.export_home_url,
            'allow_deid': has_privilege(self.request, privileges.DEIDENTIFIED_DATA),
            'use_new_exports': use_new_exports(self.domain),
            'has_excel_dashboard_access': domain_has_privilege(self.domain, EXCEL_DASHBOARD),
            'has_daily_saved_export_access': domain_has_privilege(self.domain, DAILY_SAVED_EXPORT),
        }

    def commit(self, request):
        export = self.export_instance_cls.wrap(json.loads(request.body))
        if (self.domain != export.domain
                or (export.export_format == "html" and not domain_has_privilege(self.domain, EXCEL_DASHBOARD))
                or (export.is_daily_saved_export and not domain_has_privilege(self.domain, DAILY_SAVED_EXPORT))):
            raise BadExportConfiguration()

        if not export._rev and getattr(settings, "ENTERPRISE_MODE"):
            # default auto rebuild to False for enterprise clusters
            # only do this on first save to prevent disabling on every edit
            export.auto_rebuild_enabled = False
        export.save()
        messages.success(
            request,
            mark_safe(
                _("Export <strong>{}</strong> saved.").format(
                    export.name
                )
            )
        )
        return export._id


class BaseModifyNewCustomView(BaseNewExportView):

    @use_ko_validation
    @method_decorator(require_can_edit_data)
    def dispatch(self, request, *args, **kwargs):
        return super(BaseModifyNewCustomView, self).dispatch(request, *args, **kwargs)

    @memoized
    def get_export_schema(self, domain, app_id, identifier):
        return self.export_schema_cls.generate_schema_from_builds(
            domain,
            app_id,
            identifier,
            only_process_current_builds=True,
        )

    @property
    def page_context(self):
        result = super(BaseModifyNewCustomView, self).page_context
        result['format_options'] = ["xls", "xlsx", "csv"]
        schema = self.get_export_schema(
            self.domain,
            self.request.GET.get('app_id') or getattr(self.export_instance, 'app_id'),
            self.export_instance.identifier,
        )
        result['number_of_apps_to_process'] = schema.get_number_of_apps_to_process()
        return result


@location_safe
class CreateNewCustomFormExportView(BaseModifyNewCustomView):
    urlname = 'new_custom_export_form'
    page_title = ugettext_lazy("Create Form Export")
    export_type = FORM_EXPORT

    def create_new_export_instance(self, schema):
        return self.export_instance_cls.generate_instance_from_schema(schema)

    def get(self, request, *args, **kwargs):
        app_id = request.GET.get('app_id')
        xmlns = request.GET.get('export_tag').strip('"')

        schema = self.get_export_schema(self.domain, app_id, xmlns)
        self.export_instance = self.create_new_export_instance(schema)

        return super(CreateNewCustomFormExportView, self).get(request, *args, **kwargs)


@location_safe
class CreateNewCustomCaseExportView(BaseModifyNewCustomView):
    urlname = 'new_custom_export_case'
    page_title = ugettext_lazy("Create Case Export")
    export_type = CASE_EXPORT

    def create_new_export_instance(self, schema):
        return self.export_instance_cls.generate_instance_from_schema(schema)

    def get(self, request, *args, **kwargs):
        case_type = request.GET.get('export_tag').strip('"')

        schema = self.get_export_schema(self.domain, None, case_type)
        self.export_instance = self.create_new_export_instance(schema)

        return super(CreateNewCustomCaseExportView, self).get(request, *args, **kwargs)


class DailySavedExportMixin(object):

    def _priv_check(self):
        if not domain_has_privilege(self.domain, DAILY_SAVED_EXPORT):
            raise Http404

    def dispatch(self, *args, **kwargs):
        self._priv_check()
        return super(DailySavedExportMixin, self).dispatch(*args, **kwargs)

    def create_new_export_instance(self, schema):
        instance = super(DailySavedExportMixin, self).create_new_export_instance(schema)
        instance.is_daily_saved_export = True

        span = datespan_from_beginning(self.domain_object, _get_timezone(self.domain, self.request.couch_user))
        instance.filters.date_period = DatePeriod(
            period_type="since", begin=span.startdate.date()
        )
        if not self.request.can_access_all_locations:
            accessible_location_ids = (SQLLocation.active_objects.accessible_location_ids(
                self.request.domain,
                self.request.couch_user)
            )
        else:
            accessible_location_ids = None
        instance.filters.can_access_all_locations = self.request.can_access_all_locations
        instance.filters.accessible_location_ids = accessible_location_ids

        return instance

    @property
    def report_class(self):
        return DailySavedExportListView


class DashboardFeedMixin(DailySavedExportMixin):

    def _priv_check(self):
        if not domain_has_privilege(self.domain, EXCEL_DASHBOARD):
            raise Http404

    def create_new_export_instance(self, schema):
        instance = super(DashboardFeedMixin, self).create_new_export_instance(schema)
        instance.export_format = "html"
        return instance

    @property
    def page_context(self):
        context = super(DashboardFeedMixin, self).page_context
        context['format_options'] = ["html"]
        return context

    @property
    def report_class(self):
        return DashboardFeedListView


@location_safe
class CreateNewCaseFeedView(DashboardFeedMixin, CreateNewCustomCaseExportView):
    urlname = 'new_case_feed_export'
    page_title = ugettext_lazy("Create Dashboard Feed")


@location_safe
class CreateNewFormFeedView(DashboardFeedMixin, CreateNewCustomFormExportView):
    urlname = 'new_form_feed_export'
    page_title = ugettext_lazy("Create Dashboard Feed")


@location_safe
class CreateNewDailySavedCaseExport(DailySavedExportMixin, CreateNewCustomCaseExportView):
    urlname = 'new_case_daily_saved_export'


@location_safe
class CreateNewDailySavedFormExport(DailySavedExportMixin, CreateNewCustomFormExportView):
    urlname = 'new_form_faily_saved_export'


class BaseEditNewCustomExportView(BaseModifyNewCustomView):

    @property
    def export_id(self):
        return self.kwargs.get('export_id')

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain, self.export_id])

    def get(self, request, *args, **kwargs):
        auto_select = True
        try:
            export_instance = self.export_instance_cls.get(self.export_id)
            # if the export exists we don't want to automatically select new columns
            auto_select = False
        except ResourceNotFound:
            # If it's not found, try and see if it's on the legacy system before throwing a 404
            try:
                legacy_cls = None
                if self.export_type == FORM_EXPORT:
                    legacy_cls = FormExportSchema
                elif self.export_type == CASE_EXPORT:
                    legacy_cls = CaseExportSchema

                legacy_export = legacy_cls.get(self.export_id)
                convert_export = True

                if legacy_export.converted_saved_export_id:
                    # If this is the case, this means the user has refreshed the Export page
                    # before saving, thus we've already converted, but the URL still has
                    # the legacy ID
                    export_instance = self.export_instance_cls.get(
                        legacy_export.converted_saved_export_id
                    )

                    # If the fetched export instance has been deleted, then we know that we
                    # should retry the conversion
                    convert_export = export_instance.doc_type.endswith(DELETED_SUFFIX)

                if convert_export:
                    export_instance, meta = convert_saved_export_to_export_instance(
                        self.domain,
                        legacy_export,
                    )

            except ResourceNotFound:
                raise Http404()
            except Exception:
                messages.error(
                    request,
                    mark_safe(
                        _("Export failed to convert to new version. Try creating another export")
                    )
                )
                return HttpResponseRedirect(self.export_home_url)

        schema = self.get_export_schema(
            self.domain,
            self.request.GET.get('app_id') or getattr(export_instance, 'app_id'),
            export_instance.identifier
        )
        self.export_instance = self.export_instance_cls.generate_instance_from_schema(
            schema,
            saved_export=export_instance,
            auto_select=auto_select
        )
        for message in self.export_instance.error_messages():
            messages.error(request, message)
        return super(BaseEditNewCustomExportView, self).get(request, *args, **kwargs)


class EditNewCustomFormExportView(BaseEditNewCustomExportView):
    urlname = 'edit_new_custom_export_form'
    page_title = ugettext_lazy("Edit Form Export")
    export_type = FORM_EXPORT


class EditNewCustomCaseExportView(BaseEditNewCustomExportView):
    urlname = 'edit_new_custom_export_case'
    page_title = ugettext_lazy("Edit Case Export")
    export_type = CASE_EXPORT


class EditCaseFeedView(DashboardFeedMixin, EditNewCustomCaseExportView):
    urlname = 'edit_case_feed_export'
    page_title = ugettext_lazy("Edit Case Feed")


class EditFormFeedView(DashboardFeedMixin, EditNewCustomFormExportView):
    urlname = 'edit_form_feed_export'
    page_title = ugettext_lazy("Edit Form Feed")


class EditCaseDailySavedExportView(DailySavedExportMixin, EditNewCustomCaseExportView):
    urlname = 'edit_case_daily_saved_export'


class EditFormDailySavedExportView(DailySavedExportMixin, EditNewCustomFormExportView):
    urlname = 'edit_form_daily_saved_export'


class DeleteNewCustomExportView(BaseModifyNewCustomView):
    urlname = 'delete_new_custom_export'
    http_method_names = ['post']
    is_async = False

    @property
    def export_id(self):
        return self.kwargs.get('export_id')

    @property
    @memoized
    def export_instance(self):
        try:
            return self.export_instance_cls.get(self.export_id)
        except ResourceNotFound:
            raise Http404()

    def commit(self, request):
        self.export_type = self.kwargs.get('export_type')
        export = self.export_instance
        export.delete()
        messages.success(
            request,
            mark_safe(
                _("Export <strong>{}</strong> was deleted.").format(
                    export.name
                )
            )
        )
        return export._id

    @property
    @memoized
    def report_class(self):
        # The user will be redirected to the view class returned by this function after a successful deletion
        if self.export_instance.is_daily_saved_export and use_new_daily_saved_exports_ui(self.domain):
            if self.export_instance.export_format == "html":
                return DashboardFeedListView
            return DailySavedExportListView
        elif self.export_instance.type == FORM_EXPORT:
            return FormExportListView
        elif self.export_instance.type == CASE_EXPORT:
            return CaseExportListView
        else:
            raise Exception("Export does not match any export list views!")


class GenericDownloadNewExportMixin(object):
    """
    Supporting class for new style export download views
    """
    # Form used for rendering filters
    filter_form_class = None
    # To serve filters for export from mobile_user_and_group_slugs
    export_filter_class = None
    mobile_user_and_group_slugs_regex = re.compile(
        '(emw=|case_list_filter=|location_restricted_mobile_worker=){1}([^&]*)(&){0,1}'
    )

    def _get_download_task(self, in_data):
        export_filters, export_specs = self._process_filters_and_specs(in_data)
        export_instances = [self._get_export(self.domain, spec['export_id']) for spec in export_specs]
        self._check_deid_permissions(export_instances)
        self._check_export_size(export_instances, export_filters)

        return get_export_download(
            export_instances=export_instances,
            filters=export_filters,
            filename=self._get_filename(export_instances)
        )

    def _get_filename(self, export_instances):
        if len(export_instances) > 1:
            return "{}_custom_bulk_export_{}".format(
                self.domain,
                date.today().isoformat()
            )
        else:
            return "{} {}".format(
                export_instances[0].name,
                date.today().isoformat()
            )

    def _check_deid_permissions(self, export_instances):
        # if any export is de-identified, check that
        # the requesting domain has access to the deid feature.
        if not self.has_deid_view_permissions:
            for instance in export_instances:
                if instance.is_deidentified:
                    raise ExportAsyncException(
                        _("You do not have permission to export this "
                        "De-Identified export.")
                    )

    def _check_export_size(self, export_instances, filters):
        count = 0
        for instance in export_instances:
            count += get_export_size(instance, filters)
        if count > MAX_EXPORTABLE_ROWS and not PAGINATED_EXPORTS.enabled(self.domain):
            raise ExportAsyncException(
                _("This export contains %(row_count)s rows. Please change the "
                  "filters to be less than %(max_rows)s rows.") % {
                    'row_count': count,
                    'max_rows': MAX_EXPORTABLE_ROWS
                }
            )

    @property
    def page_context(self):
        parent_context = super(GenericDownloadNewExportMixin, self).page_context
        if self.export_filter_class:
            parent_context['dynamic_filters'] = self.export_filter_class(
                self.request, self.request.domain
            ).render()
        return parent_context

    def _get_mobile_user_and_group_slugs(self, filter_slug):
        matches = self.mobile_user_and_group_slugs_regex.findall(filter_slug)
        return [n[1] for n in matches]

    def _process_filters_and_specs(self, in_data):
        """
        Returns a the export filters and a list of JSON export specs
        Override to hook fetching mobile_user_and_group_slugs
        """
        filter_form_data, export_specs = self._get_form_data_and_specs(in_data)
        mobile_user_and_group_slugs = self._get_mobile_user_and_group_slugs(
            filter_form_data[ExpandedMobileWorkerFilter.slug]
        )
        try:
            export_filter = self.get_filters(filter_form_data, mobile_user_and_group_slugs)
        except ExportFormValidationException:
            raise ExportAsyncException(
                _("Form did not validate.")
            )

        return export_filter, export_specs


@location_safe
class DownloadNewFormExportView(GenericDownloadNewExportMixin, DownloadFormExportView):
    urlname = 'new_export_download_forms'
    filter_form_class = EmwfFilterFormExport
    export_filter_class = ExpandedMobileWorkerFilter

    def _get_export(self, domain, export_id):
        return FormExportInstance.get(export_id)

    def get_filters(self, filter_form_data, mobile_user_and_group_slugs):
        filter_form = self._get_filter_form(filter_form_data)
        if not self.request.can_access_all_locations:
            accessible_location_ids = (SQLLocation.active_objects.accessible_location_ids(
                self.request.domain,
                self.request.couch_user)
            )
        else:
            accessible_location_ids = None
        form_filters = filter_form.get_form_filter(
            mobile_user_and_group_slugs, self.request.can_access_all_locations, accessible_location_ids
        )
        return form_filters

    def get_multimedia_task_kwargs(self, in_data, filter_form, export_object, download_id):
        filter_slug = in_data['form_data'][ExpandedMobileWorkerFilter.slug]
        mobile_user_and_group_slugs = self._get_mobile_user_and_group_slugs(filter_slug)
        return filter_form.get_multimedia_task_kwargs(export_object, download_id, mobile_user_and_group_slugs)


class BulkDownloadNewFormExportView(DownloadNewFormExportView):
    urlname = 'new_bulk_download_forms'
    page_title = ugettext_noop("Download Form Exports")
    filter_form_class = EmwfFilterFormExport
    export_filter_class = ExpandedMobileWorkerFilter

    @allow_remote_invocation
    def has_multimedia(self, in_data):
        return False


@location_safe
class DownloadNewCaseExportView(GenericDownloadNewExportMixin, DownloadCaseExportView):
    urlname = 'new_export_download_cases'
    filter_form_class = FilterCaseESExportDownloadForm
    export_filter_class = CaseListFilter

    def _get_export(self, domain, export_id):
        return CaseExportInstance.get(export_id)

    def get_filters(self, filter_form_data, mobile_user_and_group_slugs):
        filter_form = self._get_filter_form(filter_form_data)
        if not self.request.can_access_all_locations:
            accessible_location_ids = (SQLLocation.active_objects.accessible_location_ids(
                self.request.domain,
                self.request.couch_user)
            )
        else:
            accessible_location_ids = None
        form_filters = filter_form.get_case_filter(
            mobile_user_and_group_slugs, self.request.can_access_all_locations, accessible_location_ids
        )
        return form_filters


class DownloadNewSmsExportView(GenericDownloadNewExportMixin, BaseDownloadExportView):
    urlname = 'new_export_download_sms'
    page_title = ugettext_noop("Export SMS")
    form_or_case = None
    filter_form_class = FilterSmsESExportDownloadForm
    export_id = None
    sms_export = True

    @staticmethod
    def get_export_schema(domain, include_metadata):
        return SMSExportDataSchema.get_latest_export_schema(domain, include_metadata)

    @property
    def export_list_url(self):
        return None

    @property
    @memoized
    def download_export_form(self):
        return self.filter_form_class(
            self.domain_object,
            timezone=self.timezone,
            initial={
                'type_or_group': 'type',
            },
        )

    @property
    def parent_pages(self):
        return []

    def _get_filter_form(self, filter_form_data):
        filter_form = self.filter_form_class(
            self.domain_object, self.timezone, filter_form_data,
        )
        if not filter_form.is_valid():
            raise ExportFormValidationException()
        return filter_form

    def _get_export(self, domain, export_id):
        include_metadata = MESSAGE_LOG_METADATA.enabled_for_request(self.request)
        return SMSExportInstance._new_from_schema(
            SMSExportDataSchema.get_latest_export_schema(domain, include_metadata)
        )

    def get_filters(self, filter_form_data, mobile_user_and_group_slugs):
        filter_form = self._get_filter_form(filter_form_data)
        return filter_form.get_filter()


class GenerateSchemaFromAllBuildsView(View):
    urlname = 'build_full_schema'

    def export_cls(self, type_):
        return CaseExportDataSchema if type_ == CASE_EXPORT else FormExportDataSchema

    def get(self, request, *args, **kwargs):
        download_id = request.GET.get('download_id')
        download = DownloadBase.get(download_id)
        if download is None:
            return json_response({
                'download_id': download_id,
                'progress': None,
            })

        status = get_task_status(download.task)
        return json_response({
            'download_id': download_id,
            'success': status.success(),
            'failed': status.failed(),
            'missing': status.missing(),
            'not_started': status.not_started(),
            'progress': status.progress._asdict(),
        })

    def post(self, request, *args, **kwargs):
        type_ = request.POST.get('type')
        assert type_ in [CASE_EXPORT, FORM_EXPORT], 'Unrecogized export type {}'.format(type_)
        download = DownloadBase()
        download.set_task(generate_schema_for_all_builds.delay(
            self.export_cls(type_),
            request.domain,
            request.POST.get('app_id'),
            request.POST.get('identifier'),
        ))
        download.save()
        return json_response({
            'download_id': download.download_id
        })


def can_download_daily_saved_export(export, domain, couch_user):
    if (export.is_deidentified
        and user_can_view_deid_exports(domain, couch_user)
    ):
        return True
    elif export.type == FORM_EXPORT and has_permission_to_view_report(
            couch_user, domain, FORM_EXPORT_PERMISSION):
        return True
    elif export.type == CASE_EXPORT and has_permission_to_view_report(
            couch_user, domain, CASE_EXPORT_PERMISSION):
        return True
    return False


@login_and_domain_required
@require_POST
def add_export_email_request(request, domain):
    download_id = request.POST.get('download_id')
    user_id = request.couch_user.user_id
    if download_id is None or user_id is None:
        return HttpResponseBadRequest(ugettext_lazy('Download ID or User ID blank/not provided'))
    try:
        download_context = get_download_context(download_id)
    except TaskFailedError:
        return HttpResponseServerError(ugettext_lazy('Export failed'))
    if download_context.get('is_ready', False):
        try:
            couch_user = CouchUser.get_by_user_id(user_id, domain=domain)
        except CouchUser.AccountTypeError:
            return HttpResponseBadRequest(ugettext_lazy('Invalid user'))
        if couch_user is not None:
            process_email_request(domain, download_id, couch_user.get_email())
    else:
        EmailExportWhenDoneRequest.objects.create(domain=domain, download_id=download_id, user_id=user_id)
    return HttpResponse(ugettext_lazy('Export e-mail request sent.'))


@location_safe
@csrf_exempt
@api_auth
@require_GET
def download_daily_saved_export(req, domain, export_instance_id):
    with CriticalSection(['export-last-accessed-{}'.format(export_instance_id)]):
        try:
            export_instance = get_properly_wrapped_export_instance(export_instance_id)
        except ResourceNotFound:
            raise Http404(_("Export not found"))

        assert domain == export_instance.domain

        if export_instance.export_format == "html":
            if not domain_has_privilege(domain, EXCEL_DASHBOARD):
                raise Http404
        elif export_instance.is_daily_saved_export:
            if not domain_has_privilege(domain, DAILY_SAVED_EXPORT):
                raise Http404

        if not export_instance.filters.is_location_safe_for_user(req):
            return location_restricted_response(req)

        if not can_download_daily_saved_export(export_instance, domain, req.couch_user):
            raise Http404

        if export_instance.export_format == "html":
            message = "Download Excel Dashboard"
        else:
            message = "Download Saved Export"
        track_workflow(req.couch_user.username, message, properties={
            'domain': domain,
            'is_dimagi': req.couch_user.is_dimagi
        })

        if should_update_export(export_instance.last_accessed):
            try:
                from corehq.apps.export.tasks import rebuild_export_task
                rebuild_export_task.delay(export_instance_id)
            except Exception:
                notify_exception(
                    req,
                    'Failed to rebuild export during download',
                    {
                        'export_instance_id': export_instance_id,
                        'domain': domain,
                    },
                )

        export_instance.last_accessed = datetime.utcnow()
        export_instance.save()

    payload = export_instance.get_payload(stream=True)
    return build_download_saved_export_response(
        payload, export_instance.export_format, export_instance.filename
    )


class CopyExportView(View):
    urlname = 'copy_export'

    @method_decorator(login_and_domain_required)
    def dispatch(self, request, *args, **kwargs):
        if not self.request.couch_user.can_edit_data():
            raise Http404
        else:
            return super(CopyExportView, self).dispatch(request, *args, **kwargs)

    def get(self, request, domain, export_id, *args, **kwargs):
        try:
            export = get_properly_wrapped_export_instance(export_id)
        except ResourceNotFound:
            messages.error(request, _('You can only copy new exports.'))
        else:
            new_export = export.copy_export()
            new_export.save()
        referer = request.META.get('HTTP_REFERER', reverse('data_interfaces_default', args=[domain]))
        return HttpResponseRedirect(referer)
