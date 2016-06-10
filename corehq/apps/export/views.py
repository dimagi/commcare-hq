from datetime import datetime, date, timedelta
from couchdbkit import ResourceNotFound
from django.conf import settings
from django.contrib import messages
from django.contrib.humanize.templatetags.humanize import naturaltime
from django.core.exceptions import SuspiciousOperation
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, HttpResponseBadRequest, Http404
from django.template.defaultfilters import filesizeformat
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET

from corehq.apps.export.export import get_export_download
from corehq.apps.reports.views import should_update_export, \
    build_download_saved_export_response, require_form_export_permission
from corehq.form_processor.interfaces.dbaccessors import FormAccessors
from django_prbac.utils import has_privilege
from django.utils.decorators import method_decorator
import json
from django.utils.safestring import mark_safe

from djangular.views.mixins import JSONResponseMixin, allow_remote_invocation
import pytz
from corehq import privileges
from corehq import toggles
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.app_manager.fields import ApplicationDataRMIHelper
from corehq.apps.data_interfaces.dispatcher import require_can_edit_data
from corehq.apps.domain.decorators import login_and_domain_required, \
    login_or_digest_or_basic_or_apikey
from corehq.apps.export.utils import (
    convert_saved_export_to_export_instance,
    revert_new_exports,
)
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
    FilterFormCouchExportDownloadForm,
    FilterCaseCouchExportDownloadForm,
    FilterFormESExportDownloadForm,
    FilterCaseESExportDownloadForm,
)
from corehq.apps.export.models import (
    FormExportDataSchema,
    CaseExportDataSchema,
    FormExportInstance,
    CaseExportInstance,
)
from corehq.apps.export.const import (
    FORM_EXPORT,
    CASE_EXPORT,
)
from corehq.apps.export.dbaccessors import (
    get_form_export_instances,
    get_case_export_instances,
    get_properly_wrapped_export_instance,
)
from corehq.apps.groups.models import Group
from corehq.apps.reports.dbaccessors import touch_exports
from corehq.apps.reports.display import xmlns_to_name
from corehq.apps.reports.export import CustomBulkExportHelper
from corehq.apps.reports.exportfilters import default_form_filter
from corehq.apps.reports.models import FormExportSchema, CaseExportSchema, \
    HQGroupExportConfiguration
from corehq.apps.reports.util import datespan_from_beginning
from corehq.apps.reports.tasks import rebuild_export_task
from corehq.apps.settings.views import BaseProjectDataView
from corehq.apps.style.decorators import (
    use_select2,
    use_daterangepicker,
    use_jquery_ui,
    use_angular_js)
from corehq.apps.style.forms.widgets import DateRangePickerWidget
from corehq.apps.style.utils import format_angular_error, format_angular_success
from corehq.apps.users.decorators import get_permission_name
from corehq.apps.users.models import Permissions
from corehq.apps.users.permissions import FORM_EXPORT_PERMISSION, CASE_EXPORT_PERMISSION, \
    DEID_EXPORT_PERMISSION
from corehq.util.couch import get_document_or_404_lite
from corehq.util.timezones.utils import get_timezone_for_user
from corehq.util.soft_assert import soft_assert
from couchexport.models import SavedExportSchema, ExportSchema
from couchexport.schema import build_latest_schema
from couchexport.util import SerializableFunction
from couchforms.filters import instances
from dimagi.utils.decorators.memoized import memoized
from django.utils.translation import ugettext as _, ugettext_noop, ugettext_lazy
from dimagi.utils.logging import notify_exception
from dimagi.utils.parsing import json_format_date
from dimagi.utils.web import json_response
from soil import DownloadBase
from soil.exceptions import TaskFailedError
from soil.util import get_download_context


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
    def has_view_permissions(self):
        if self.form_or_case == 'form':
            report_to_check = FORM_EXPORT_PERMISSION
        elif self.form_or_case == 'case':
            report_to_check = CASE_EXPORT_PERMISSION
        return (self.request.couch_user.can_view_reports()
                or self.request.couch_user.has_permission(
                    self.domain,
                    get_permission_name(Permissions.view_report),
                    data=report_to_check))

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


class BaseDownloadExportView(ExportsPermissionsMixin, JSONResponseMixin, BaseProjectDataView):
    template_name = 'export/download_export.html'
    http_method_names = ['get', 'post']
    show_sync_to_dropbox = False  # remove when DBox issue is resolved.
    show_date_range = False
    check_for_multimedia = False
    filter_form_class = None

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
        raise Http404(_(u"Export not found"))

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
        elif self.export_id:
            exports = [self._get_export(self.domain, self.export_id)]

        if not self.has_view_permissions:
            if self.has_deid_view_permissions:
                exports = filter(lambda x: x.is_safe, exports)
            else:
                raise Http404()

        # if there are no exports, this page doesn't exist
        if not exports:
            raise Http404()

        exports = map(
            lambda e: self.download_export_form.format_export_data(e),
            exports
        )
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
            filename=u"{}{}".format(export_object.name,
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
            return format_angular_error(e.message)
        except Exception as e:
            return format_angular_error(
                e.message,
                log_error=True,
                exception=e,
            )
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
        raise Http404(_(u"Export not found"))

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
            has_multimedia = FormAccessors(self.domain).forms_have_multimedia(
                export_object.app_id,
                getattr(export_object, 'xmlns', '')
            )
        except Exception as e:
            return format_angular_error(e.message)
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
            task_kwargs = filter_form.get_multimedia_task_kwargs(
                export_object, download.download_id
            )
            from corehq.apps.reports.tasks import build_form_multimedia_zip
            download.set_task(build_form_multimedia_zip.delay(**task_kwargs))
        except Exception as e:
            return format_angular_error(e)
        return format_angular_success({
            'download_id': download.download_id,
        })

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
            self.domain_object, filter_form_data
        )
        if not filter_form.is_valid():
            raise ExportFormValidationException()
        return filter_form


class BaseExportListView(ExportsPermissionsMixin, JSONResponseMixin, BaseProjectDataView):
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
        return super(BaseExportListView, self).dispatch(request, *args, **kwargs)

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
        raise NotImplementedError("must implement saved_exports")

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
                                download_url=None):
        """
        Return a dictionary containing details about an emailed export.
        This will eventually be passed to an Angular controller.
        """
        file_data = {}
        if has_file:
            file_data = self._fmt_emailed_export_fileData(
                has_file, file_id, size, last_updated, last_accessed, download_url
            )

        return {
            'groupId': group_id,  # This can be removed when we're off legacy exports
            'hasFile': has_file,
            'index': index,  # This can be removed when we're off legacy exports
            'fileData': file_data,
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

        emailed_exports = filter(
            lambda x: x.config.index[-1] == export.get_id,
            self.daily_emailed_exports
        )

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
            has_file=export.has_file(),
            file_id=export._id,
            size=export.file_size,
            last_updated=export.last_updated,
            last_accessed=export.last_accessed,
            download_url=reverse(
                'download_daily_saved_export', args=[self.domain, export._id]
            ),
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
                saved_exports = filter(lambda x: x.is_safe, saved_exports)
            saved_exports = map(self.fmt_export_data, saved_exports)
        except Exception as e:
            return format_angular_error(
                _("Issue fetching list of exports: {}").format(e),
                log_error=True,
                exception=e,
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
    def create_export_form(self):
        """Returns a django form that gets the information necessary to create
        an export tag, which is the first step in creating a new export.

        This is either an instance of:
        - CreateFormExportTagForm
        - CreateCaseExportTagForm

        This form is what will interact with the DrilldownToFormController in
        hq.app_data_drilldown.ng.js
        """
        raise NotImplementedError("must implement create_export_form")

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

    def get_emailed_indexes(self, email_group):
        """Return a list of indexes of the components of the HQGroupExportConfiguration
        ExportConfiguration list"""
        raise NotImplementedError("must implement get_emailed_indexes")

    def update_emailed_es_export_data(self, in_data):
        from corehq.apps.export.tasks import rebuild_export_task
        export_instance_id = in_data['export']['id']
        export_instance = get_properly_wrapped_export_instance(export_instance_id)
        rebuild_export_task.delay(export_instance)
        return format_angular_success({})

    @allow_remote_invocation
    def update_emailed_export_data(self, in_data):
        if not in_data['export']['isLegacy']:
            return self.update_emailed_es_export_data(in_data)

        group_id = in_data['component']['groupId']
        relevant_group = filter(lambda g: g.get_id, self.emailed_export_groups)[0]
        indexes = map(lambda x: x[0].index, relevant_group.all_exports)
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
                _("Problem getting link to custom export form: {}").format(e),
            )
        return format_angular_success({
            'url': create_url,
        })


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
        exports = FormExportSchema.get_stale_exports(self.domain)
        new_exports = get_form_export_instances(self.domain)
        if toggles.NEW_EXPORTS.enabled(self.domain):
            exports += new_exports
        else:
            exports += revert_new_exports(new_exports)
        if not self.has_deid_view_permissions:
            exports = filter(lambda x: not x.is_safe, exports)
        return sorted(exports, key=lambda x: x.name)

    @property
    @memoized
    def daily_emailed_exports(self):
        all_form_exports = []
        for group in self.emailed_export_groups:
            all_form_exports.extend(group.form_exports)
        return all_form_exports

    @property
    @memoized
    def create_export_form(self):
        return CreateFormExportTagForm()

    @property
    def create_export_form_title(self):
        return _("Select a Form to Export")

    def fmt_export_data(self, export):
        if toggles.NEW_EXPORTS.enabled(self.domain):
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
        except Exception as e:
            return format_angular_error(
                _("Problem getting Create Export Form: {} {}").format(
                    e.__class__, e
                ),
            )
        return format_angular_success(response)

    def get_create_export_url(self, form_data):
        create_form = CreateFormExportTagForm(form_data)
        if not create_form.is_valid():
            raise ExportFormValidationException()

        app_id = create_form.cleaned_data['application']
        form_xmlns = create_form.cleaned_data['form']
        if toggles.NEW_EXPORTS.enabled(self.domain):
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
        exports = CaseExportSchema.get_stale_exports(self.domain)
        new_exports = get_case_export_instances(self.domain)
        if toggles.NEW_EXPORTS.enabled(self.domain):
            exports += new_exports
        else:
            exports += revert_new_exports(new_exports)
        if not self.has_deid_view_permissions:
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
        if toggles.NEW_EXPORTS.enabled(self.domain):
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
        except Exception as e:
            return format_angular_error(
                _("Problem getting Create Export Form: {}").format(e.message),
                log_error=True,
                exception=e,
            )
        return format_angular_success(response)

    def get_create_export_url(self, form_data):
        create_form = CreateCaseExportTagForm(form_data)
        if not create_form.is_valid():
            raise ExportFormValidationException()
        case_type = create_form.cleaned_data['case_type']
        if toggles.NEW_EXPORTS.enabled(self.domain):
            cls = CreateNewCustomCaseExportView
        else:
            cls = CreateCustomCaseExportView
        return reverse(
            cls.urlname,
            args=[self.domain],
        ) + ('?export_tag="{export_tag}"'.format(
            export_tag=case_type,
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
    def page_context(self):
        return {
            'export_instance': self.export_instance,
            'export_home_url': self.export_home_url,
            'allow_deid': has_privilege(self.request, privileges.DEIDENTIFIED_DATA),
        }

    def commit(self, request):
        export = self.export_instance_cls.wrap(json.loads(request.body))
        export.save()
        messages.success(
            request,
            mark_safe(
                _(u"Export <strong>{}</strong> created.").format(
                    export.name
                )
            )
        )
        return export._id


class BaseModifyNewCustomView(BaseNewExportView):

    @method_decorator(require_can_edit_data)
    def dispatch(self, request, *args, **kwargs):
        return super(BaseModifyNewCustomView, self).dispatch(request, *args, **kwargs)


class CreateNewCustomFormExportView(BaseModifyNewCustomView):
    urlname = 'new_custom_export_form'
    page_title = ugettext_lazy("Create Form Export")
    export_type = FORM_EXPORT

    def get(self, request, *args, **kwargs):
        app_id = request.GET.get('app_id')
        xmlns = request.GET.get('export_tag').strip('"')

        schema = FormExportDataSchema.generate_schema_from_builds(
            self.domain,
            app_id,
            xmlns,
            force_rebuild=True,
        )
        self.export_instance = self.export_instance_cls.generate_instance_from_schema(schema)

        return super(CreateNewCustomFormExportView, self).get(request, *args, **kwargs)


class CreateNewCustomCaseExportView(BaseModifyNewCustomView):
    urlname = 'new_custom_export_case'
    page_title = ugettext_lazy("Create Case Export")
    export_type = CASE_EXPORT

    def get(self, request, *args, **kwargs):
        case_type = request.GET.get('export_tag').strip('"')

        schema = CaseExportDataSchema.generate_schema_from_builds(
            self.domain,
            case_type,
            force_rebuild=True,
        )
        self.export_instance = self.export_instance_cls.generate_instance_from_schema(schema)

        return super(CreateNewCustomCaseExportView, self).get(request, *args, **kwargs)


class BaseEditNewCustomExportView(BaseModifyNewCustomView):

    @property
    def export_id(self):
        return self.kwargs.get('export_id')

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain, self.export_id])

    def commit(self, request):
        export = self.export_instance_cls.wrap(json.loads(request.body))
        export.save()
        messages.success(
            request,
            mark_safe(
                _(u"Export <strong>{}</strong> was saved.").format(
                    export.name
                )
            )
        )
        return export._id

    def get_export_schema(self, export_instance):
        raise NotImplementedError()

    def get(self, request, *args, **kwargs):
        try:
            export_instance = self.export_instance_cls.get(self.export_id)
        except ResourceNotFound:
            # If it's not found, try and see if it's on the legacy system before throwing a 404
            try:
                legacy_cls = None
                if self.export_type == FORM_EXPORT:
                    legacy_cls = FormExportSchema
                elif self.export_type == CASE_EXPORT:
                    legacy_cls = CaseExportSchema

                legacy_export = legacy_cls.get(self.export_id)

                if legacy_export.converted_saved_export_id:
                    # If this is the case, this means the user has refreshed the Export page
                    # before saving, thus we've already converted, but the URL still has
                    # the legacy ID
                    export_instance = self.export_instance_cls.get(
                        legacy_export.converted_saved_export_id
                    )
                else:
                    export_instance = convert_saved_export_to_export_instance(
                        self.domain,
                        legacy_export,
                    )

            except ResourceNotFound:
                raise Http404()
            except Exception, e:
                _soft_assert = soft_assert('{}@{}'.format('brudolph', 'dimagi.com'))
                _soft_assert(False, 'Failed to convert export {}. {}'.format(self.export_id, e))
                messages.error(
                    request,
                    mark_safe(
                        _("Export failed to convert to new version. Try creating another export")
                    )
                )
                return HttpResponseRedirect(self.export_home_url)

        schema = self.get_export_schema(export_instance)
        self.export_instance = self.export_instance_cls.generate_instance_from_schema(
            schema,
            saved_export=export_instance,
        )
        return super(BaseEditNewCustomExportView, self).get(request, *args, **kwargs)


class EditNewCustomFormExportView(BaseEditNewCustomExportView):
    urlname = 'edit_new_custom_export_form'
    page_title = ugettext_lazy("Edit Form Export")
    export_type = FORM_EXPORT

    def get_export_schema(self, export_instance):
        return FormExportDataSchema.generate_schema_from_builds(
            self.domain,
            export_instance.app_id,
            export_instance.xmlns,
        )


class EditNewCustomCaseExportView(BaseEditNewCustomExportView):
    urlname = 'edit_new_custom_export_case'
    page_title = ugettext_lazy("Edit Case Export")
    export_type = CASE_EXPORT

    def get_export_schema(self, export_instance):
        return CaseExportDataSchema.generate_schema_from_builds(
            self.domain,
            export_instance.case_type,
        )


class DeleteNewCustomExportView(BaseModifyNewCustomView):
    urlname = 'delete_new_custom_export'
    http_method_names = ['post']
    is_async = False

    @property
    def export_id(self):
        return self.kwargs.get('export_id')

    def commit(self, request):
        self.export_type = self.kwargs.get('export_type')
        try:
            export = self.export_instance_cls.get(self.export_id)
        except ResourceNotFound:
            raise Http404()

        export.delete()
        messages.success(
            request,
            mark_safe(
                _(u"Export <strong>{}</strong> was deleted.").format(
                    export.name
                )
            )
        )
        return export._id


class GenericDownloadNewExportMixin(object):
    """
    Supporting class for new style export download views
    """

    def _get_download_task(self, in_data):
        export_filters, export_specs = self._process_filters_and_specs(in_data)
        export_instances = [self._get_export(self.domain, spec['export_id']) for spec in export_specs]
        self._check_deid_permissions(export_instances)

        return get_export_download(
            export_instances=export_instances,
            filters=export_filters,
            filename=self._get_filename(export_instances)
        )

    def _get_filename(self, export_instances):
        if len(export_instances) > 1:
            return u"{}_custom_bulk_export_{}".format(
                self.domain,
                date.today().isoformat()
            )
        else:
            return u"{} {}".format(
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


class DownloadNewFormExportView(GenericDownloadNewExportMixin, DownloadFormExportView):
    urlname = 'new_export_download_forms'
    filter_form_class = FilterFormESExportDownloadForm

    def _get_export(self, domain, export_id):
        return FormExportInstance.get(export_id)

    def get_filters(self, filter_form_data):
        filter_form = self._get_filter_form(filter_form_data)
        form_filters = filter_form.get_form_filter()
        return form_filters


class BulkDownloadNewFormExportView(DownloadNewFormExportView):
    urlname = 'new_bulk_download_forms'
    page_title = ugettext_noop("Download Form Exports")


class DownloadNewCaseExportView(GenericDownloadNewExportMixin, DownloadCaseExportView):
    urlname = 'new_export_download_cases'
    filter_form_class = FilterCaseESExportDownloadForm

    def _get_export(self, domain, export_id):
        return CaseExportInstance.get(export_id)

    def get_filters(self, filter_form_data):
        filter_form = self._get_filter_form(filter_form_data)
        form_filters = filter_form.get_case_filter()
        return form_filters


@csrf_exempt
@login_or_digest_or_basic_or_apikey(default='digest')
@require_form_export_permission
@require_GET
def download_daily_saved_export(req, domain, export_instance_id):
    export_instance = get_properly_wrapped_export_instance(export_instance_id)
    assert domain == export_instance.domain
    if should_update_export(export_instance.last_accessed):
        try:
            from corehq.apps.export.tasks import rebuild_export_task
            rebuild_export_task.delay(export_instance)
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
