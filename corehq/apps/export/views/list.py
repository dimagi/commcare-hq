import json
from datetime import datetime, timedelta

from django.conf import settings
from django.contrib.humanize.templatetags.humanize import naturaltime
from django.http import Http404
from django.template.defaultfilters import filesizeformat
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.safestring import mark_safe
from django.utils.html import format_html
from django.utils.functional import lazy
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy, gettext_noop
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from django.contrib import messages
from django.core.cache import cache

from couchdbkit import ResourceNotFound
from memoized import memoized

from corehq.apps.accounting.decorators import requires_privilege_with_fallback
from corehq.apps.export.exceptions import ExportTooLargeException
from corehq.apps.export.views.download import DownloadDETSchemaView
from couchexport.models import Format, IntegrationFormat
from couchexport.writers import XlsLengthException
from dimagi.utils.couch import CriticalSection
from dimagi.utils.logging import notify_exception
from dimagi.utils.web import json_response

from corehq import toggles
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.analytics.tasks import track_workflow
from corehq.apps.api.resources.v0_5 import ODataCaseResource, ODataFormResource
from corehq.apps.app_manager.fields import ApplicationDataRMIHelper
from corehq.apps.domain.decorators import api_auth, login_and_domain_required
from corehq.apps.domain.models import Domain
from corehq.apps.export.const import (
    CASE_EXPORT,
    EXPORT_FAILURE_TOO_LARGE,
    EXPORT_FAILURE_UNKNOWN,
    FORM_EXPORT,
    MAX_DAILY_EXPORT_SIZE,
    MAX_NORMAL_EXPORT_SIZE,
    UNKNOWN_EXPORT_OWNER,
    SharingOption,
    BULK_CASE_EXPORT_CACHE,
)
from corehq.apps.export.dbaccessors import (
    get_brief_deid_exports,
    get_brief_exports,
    get_properly_wrapped_export_instance,
)
from corehq.apps.export.forms import (
    CreateExportTagForm,
    DashboardFeedFilterForm,
)
from corehq.apps.export.models import CaseExportInstance, FormExportInstance
from corehq.apps.export.tasks import (
    get_saved_export_task_status,
    rebuild_saved_export,
)
from corehq.apps.export.views.edit import (
    EditExportDescription,
    EditExportNameView,
)
from corehq.apps.export.views.utils import (
    ExportsPermissionsManager,
    user_can_view_deid_exports,
)
from corehq.apps.locations.models import SQLLocation
from corehq.apps.locations.permissions import (
    location_restricted_response,
    location_safe,
)
from corehq.apps.reports.views import should_update_export
from corehq.apps.settings.views import BaseProjectDataView
from corehq.apps.users.models import CouchUser
from corehq.apps.users.permissions import (
    CASE_EXPORT_PERMISSION,
    FORM_EXPORT_PERMISSION,
    has_permission_to_view_report,
)
from corehq.privileges import DAILY_SAVED_EXPORT, EXPORT_OWNERSHIP, EXCEL_DASHBOARD, ODATA_FEED
from corehq.util.download import get_download_response
from corehq.util.view_utils import absolute_reverse
from corehq.apps.data_dictionary.util import is_case_type_deprecated


mark_safe_lazy = lazy(mark_safe, str)  # TODO: replace with library function


class ExportListHelper(object):
    '''
    Encapsulates behavior that varies based on model (form, case, or sms)
    and is needed by the function-based views in this module.
    '''
    form_or_case = None         # None if this handles both forms and cases
    is_deid = False
    allow_bulk_export = True
    include_saved_filters = False

    @classmethod
    def from_request(cls, request):
        def param_is_true(param):
            return bool(json.loads(request.GET.get(param)))

        is_deid = param_is_true('is_deid')

        if param_is_true('is_odata'):
            return ODataFeedListHelper(request)

        if param_is_true('is_feed'):
            if is_deid:
                return DeIdDashboardFeedListHelper(request)
            return DashboardFeedListHelper(request)

        if param_is_true('is_daily_saved_export'):
            if is_deid:
                return DeIdDailySavedExportListHelper(request)
            return DailySavedExportListHelper(request)

        form_or_case = request.GET.get('model_type')
        if form_or_case == 'form':
            if is_deid:
                return DeIdFormExportListHelper(request)
            return FormExportListHelper(request)
        elif form_or_case == 'case':
            return CaseExportListHelper(request)

        raise ValueError("Could not determine ExportListHelper subclass")

    def __init__(self, request):
        super(ExportListHelper, self).__init__()
        self.request = request
        self.domain = request.domain
        self.permissions = ExportsPermissionsManager(self.form_or_case, self.domain, request.couch_user)

    def _priv_check(self):
        return True

    @property
    def bulk_download_url(self):
        """Returns url for bulk download
        """
        if not self.allow_bulk_export:
            return None
        raise NotImplementedError('must implement bulk_download_url')

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

        This form is what will interact with the createExportModel in export/js/export_list.js
        """
        if self.permissions.has_case_export_permissions or self.permissions.has_form_export_permissions:
            return CreateExportTagForm(self.permissions.has_form_export_permissions,
                                       self.permissions.has_case_export_permissions)

    def _can_view_export(self, export):
        if 'owner_id' not in export:
            return True
        is_not_private = export['sharing'] != SharingOption.PRIVATE
        is_owner = export['owner_id'] == self.request.couch_user.user_id
        return is_not_private or is_owner

    def get_exports_page(self, page, limit, my_exports=False):
        if not self._priv_check():
            raise Http404

        # Calls self.get_saved_exports and formats each item using self.fmt_export_data
        brief_exports = sorted(self.get_saved_exports(), key=lambda x: x['name'])
        if domain_has_privilege(self.domain, EXPORT_OWNERSHIP):
            brief_exports = [
                export for export in brief_exports
                if self._can_view_export(export)
                and ('owner_id' in export and export['owner_id'] == self.request.couch_user.user_id) == my_exports
            ]

        docs = [self.fmt_export_data(get_properly_wrapped_export_instance(e['_id']))
                for e in brief_exports[limit * (page - 1):limit * page]]
        return (docs, len(brief_exports))

    @memoized
    def get_saved_exports(self):
        """The source of the data that will be processed by fmt_export_data
        for use in the template.
        """
        if self.is_deid:
            exports = get_brief_deid_exports(self.domain, self.form_or_case)
        else:
            exports = get_brief_exports(self.domain, self.form_or_case)
        return [x for x in exports if self._should_appear_in_list(x)]

    def _should_appear_in_list(self, export):
        raise NotImplementedError("must implement _should_appear_in_list")

    def _edit_view(self, export):
        raise NotImplementedError("must implement _edit_view")

    def _download_view(self, export):
        raise NotImplementedError("must implement _download_view")

    def fmt_export_data(self, export):
        """Returns the object used for each row (per export) in the exports table.
        This data will eventually be processed as a JSON object.
        :return dict
        """
        from corehq.apps.export.views.new import DeleteNewCustomExportView
        formname = export.formname if isinstance(export, FormExportInstance) else None
        return {
            'id': export.get_id,
            'isDeid': export.is_safe,
            'name': export.name,
            'description': export.description,
            'sharing': export.sharing,
            'owner_username': (
                CouchUser.get_by_user_id(export.owner_id).username
                if export.owner_id else UNKNOWN_EXPORT_OWNER
            ),
            'can_edit': export.can_edit(self.request.couch_user),
            'exportType': export.type,
            'filters': self._get_filters(export),
            'formname': formname,
            'deleteUrl': reverse(DeleteNewCustomExportView.urlname,
                                 args=(self.domain, export.type, export.get_id)),
            'domain': self.domain,
            'type': export.type,
            'downloadUrl': reverse(self._download_view(export).urlname, args=(self.domain, export.get_id)),
            'showDetDownload': export.show_det_config_download,
            'detSchemaUrl': reverse(DownloadDETSchemaView.urlname,
                                    args=(self.domain, export.get_id)),
            'editUrl': reverse(self._edit_view(export).urlname, args=(self.domain, export.get_id)),
            'editNameUrl': reverse(EditExportNameView.urlname, args=(self.domain, export.get_id)),
            'editDescriptionUrl': reverse(EditExportDescription.urlname, args=(self.domain, export.get_id)),
            'lastBuildDuration': '',
            'addedToBulk': False,
            'emailedExport': self._get_daily_saved_export_metadata(export),
            'odataUrl': self._get_odata_url(export),
            'additionalODataUrls': self._get_additional_odata_urls(export),
        }

    def _get_additional_odata_urls(self, export):
        urls = []
        for table_id, table in enumerate(export.tables):
            if table.selected and table_id > 0:
                urls.append({
                    "label": table.label,
                    "url": self._fmt_odata_url(
                        export,
                        export.get_id + "/{}".format(table_id)
                    ),
                })
        return urls

    def _get_odata_url(self, export):
        return self._fmt_odata_url(export, export.get_id)

    def _fmt_odata_url(self, export, pk):
        resource_class = ODataCaseResource if isinstance(export, CaseExportInstance) else ODataFormResource
        return absolute_reverse(
            'api_dispatch_detail',
            kwargs={
                'domain': export.domain,
                'api_name': 'v0.5',
                'resource_name': resource_class._meta.resource_name,
                'pk': pk + '/feed',
            }
        )[:-1]  # Remove trailing forward slash for compatibility with BI tools

    @staticmethod
    def get_location_restriction_names(accessible_location_ids):
        location_restrictions = []
        if accessible_location_ids:
            locations = SQLLocation.objects.filter(location_id__in=accessible_location_ids)
            for location in locations:
                location_restrictions.append(location.display_name)
        return location_restrictions

    def _get_daily_saved_export_metadata(self, export):
        """
        Return a dictionary containing details about an emailed export.
        This will eventually be passed to javascript.
        """
        if not export.is_daily_saved_export:
            return None

        has_file = export.has_file()
        file_data = {}
        if has_file:
            download_url = self.request.build_absolute_uri(
                reverse('download_daily_saved_export', args=[self.domain, export._id]))
            file_data = self._fmt_emailed_export_fileData(
                export._id, export.file_size, export.last_updated,
                export.last_accessed, download_url
            )

        return {
            'groupId': None,  # This can be removed when we're off legacy exports
            'hasFile': has_file,
            'index': None,  # This can be removed when we're off legacy exports
            'fileData': file_data,
            'isLocationSafeForUser': export.filters.is_location_safe_for_user(self.request),
            'locationRestrictions': self.get_location_restriction_names(export.filters.accessible_location_ids),
            'taskStatus': _get_task_status_json(export._id),
            'updatingData': False,
        }

    def _get_filters(self, export):
        if self.include_saved_filters:
            return DashboardFeedFilterForm.get_form_data_from_export_instance_filters(
                export.filters, self.domain, type(export)
            )

    def _fmt_emailed_export_fileData(self, fileId, size, last_updated,
                                     last_accessed, download_url):
        """
        Return a dictionary containing details about an emailed export file.
        This will eventually be passed to an Angular controller.
        """
        cutoff_datetime = datetime.utcnow() - timedelta(days=settings.SAVED_EXPORT_ACCESS_CUTOFF)
        return {
            'fileId': fileId,
            'size': filesizeformat(size),
            'lastUpdated': naturaltime(last_updated),
            'lastAccessed': naturaltime(last_accessed),
            'showExpiredWarning': (last_accessed and last_accessed < cutoff_datetime),
            'downloadUrl': download_url,
        }


class DailySavedExportListHelper(ExportListHelper):
    allow_bulk_export = False
    include_saved_filters = True

    def _priv_check(self):
        return domain_has_privilege(self.domain, DAILY_SAVED_EXPORT)

    @property
    @memoized
    def create_export_form_title(self):
        return _("Select a model to export")

    @property
    def bulk_download_url(self):
        # Daily Saved exports do not support bulk download
        return ""

    def _should_appear_in_list(self, export):
        return (export['is_daily_saved_export']
                and not export['export_format'] == "html"
                and not export['is_odata_config']
                and not IntegrationFormat.is_integration_format(export['export_format']))

    def _edit_view(self, export):
        from corehq.apps.export.views.edit import EditFormDailySavedExportView, EditCaseDailySavedExportView
        if isinstance(export, FormExportInstance):
            return EditFormDailySavedExportView
        return EditCaseDailySavedExportView

    def _download_view(self, export):
        from corehq.apps.export.views.download import DownloadNewCaseExportView, DownloadNewFormExportView
        if isinstance(export, FormExportInstance):
            return DownloadNewFormExportView
        return DownloadNewCaseExportView

    def fmt_export_data(self, export):
        data = super(DailySavedExportListHelper, self).fmt_export_data(export)

        data.update({
            'lastBuildDuration': (str(timedelta(milliseconds=export.last_build_duration))
                                  if export.last_build_duration else ''),
            'isDailySaved': True,
            'isAutoRebuildEnabled': export.auto_rebuild_enabled,
        })
        return data


class FormExportListHelper(ExportListHelper):
    form_or_case = 'form'

    @property
    def bulk_download_url(self):
        from corehq.apps.export.views.download import BulkDownloadNewFormExportView
        return reverse(BulkDownloadNewFormExportView.urlname, args=(self.domain,))

    @property
    def create_export_form_title(self):
        return _("Select a Form to Export")

    def _should_appear_in_list(self, export):
        return (not export['is_daily_saved_export']
            and not export['is_odata_config']
            and not IntegrationFormat.is_integration_format(export['export_format']))

    def _edit_view(self, export):
        from corehq.apps.export.views.edit import EditNewCustomFormExportView
        return EditNewCustomFormExportView

    def _download_view(self, export):
        from corehq.apps.export.views.download import DownloadNewFormExportView
        return DownloadNewFormExportView


class CaseExportListHelper(ExportListHelper):
    form_or_case = 'case'
    allow_bulk_export = False

    def _should_appear_in_list(self, export):
        return (not export['is_daily_saved_export']
            and not export['is_odata_config']
            and not IntegrationFormat.is_integration_format(export['export_format']))

    def _edit_view(self, export):
        from corehq.apps.export.views.edit import EditNewCustomCaseExportView
        return EditNewCustomCaseExportView

    def _download_view(self, export):
        from corehq.apps.export.views.download import DownloadNewCaseExportView
        return DownloadNewCaseExportView

    def fmt_export_data(self, export):
        data = super(CaseExportListHelper, self).fmt_export_data(export)
        data.update({
            'case_type': export.case_type,
            'is_case_type_deprecated': is_case_type_deprecated(export.domain, export.case_type)
        })
        return data

    @property
    def create_export_form_title(self):
        return _("Select a Case Type to Export")


class DashboardFeedListHelper(DailySavedExportListHelper):
    allow_bulk_export = False

    def _priv_check(self):
        return domain_has_privilege(self.domain, EXCEL_DASHBOARD)

    def _should_appear_in_list(self, export):
        return (export['is_daily_saved_export']
                and export['export_format'] == "html"
                and not export['is_odata_config']
                and not IntegrationFormat.is_integration_format(export['export_format']))

    def _edit_view(self, export):
        from corehq.apps.export.views.edit import EditFormFeedView, EditCaseFeedView
        if isinstance(export, FormExportInstance):
            return EditFormFeedView
        return EditCaseFeedView

    def _download_view(self, export):
        from corehq.apps.export.views.download import DownloadNewCaseExportView, DownloadNewFormExportView
        if isinstance(export, FormExportInstance):
            return DownloadNewFormExportView
        return DownloadNewCaseExportView

    def fmt_export_data(self, export):
        data = super(DashboardFeedListHelper, self).fmt_export_data(export)
        data.update({
            'isFeed': True,
        })
        return data


class DeIdFormExportListHelper(FormExportListHelper):
    is_deid = True

    @property
    def create_export_form(self):
        return None


class DeIdDailySavedExportListHelper(DailySavedExportListHelper):
    is_deid = True

    @property
    def create_export_form(self):
        return None


class DeIdDashboardFeedListHelper(DashboardFeedListHelper):
    is_deid = True

    @property
    def create_export_form(self):
        return None


class BaseExportListView(BaseProjectDataView):
    template_name = 'export/export_list.html'
    lead_text = mark_safe_lazy(gettext_lazy(  # nosec: no user input
        '''
        Exports are a way to download data in a variety of formats (CSV, Excel, etc.)
        for use in third-party data analysis tools.
    '''))
    is_odata = False
    page_title = gettext_lazy("Export Form Data")

    @method_decorator(login_and_domain_required)
    def dispatch(self, request, *args, **kwargs):
        self.permissions = ExportsPermissionsManager(self.form_or_case, request.domain, request.couch_user)
        self.permissions.access_list_exports_or_404(is_deid=self.is_deid, is_odata=self.is_odata)

        return super(BaseExportListView, self).dispatch(request, *args, **kwargs)

    @property
    def page_context(self):
        return {
            'create_export_form': self.create_export_form if not self.is_deid else None,
            'create_export_form_title': self.create_export_form_title if not self.is_deid else None,
            'bulk_download_url': self.bulk_download_url,
            'allow_bulk_export': self.allow_bulk_export,
            'has_edit_permissions': self.permissions.has_edit_permissions,
            'is_deid': self.is_deid,
            'is_odata': self.is_odata,
            "export_type_caps": _("Export"),
            "export_type": _("export"),
            "export_type_caps_plural": _("Exports"),
            "export_type_plural": _("exports"),
            'my_export_type': _('My Exports'),
            'shared_export_type': _('Exports Shared with Me'),
            "model_type": self.form_or_case,
            "static_model_type": True,
            'max_normal_export_size': MAX_NORMAL_EXPORT_SIZE,
            'max_daily_export_size': MAX_DAILY_EXPORT_SIZE,
            'lead_text': self.lead_text,
            'export_ownership_enabled': domain_has_privilege(self.domain, EXPORT_OWNERSHIP),
            "export_filter_form": (
                DashboardFeedFilterForm(
                    self.domain_object,
                    couch_user=self.request.couch_user,
                ) if self.include_saved_filters else None
            ),
            'create_url': '#createExportOptionsModal',
        }


def _get_task_status_json(export_instance_id):
    status = get_saved_export_task_status(export_instance_id)
    failure_reason = None
    if status.failed():
        failure_reason = EXPORT_FAILURE_TOO_LARGE if \
            isinstance(status.exception, ExportTooLargeException) else \
            EXPORT_FAILURE_UNKNOWN

    return {
        'percentComplete': status.progress.percent or 0,
        'started': status.started(),
        'success': status.success(),
        'failed': failure_reason,
        'justFinished': False,
    }


@login_and_domain_required
@require_GET
@location_safe
def get_exports_page(request, domain):
    permissions = ExportsPermissionsManager(request.GET.get('model_type'), domain, request.couch_user)
    permissions.access_list_exports_or_404(
        is_deid=json.loads(request.GET.get('is_deid')),
        is_odata=json.loads(request.GET.get('is_odata'))
    )
    helper = ExportListHelper.from_request(request)
    page = int(request.GET.get('page', 1))
    limit = int(request.GET.get('limit', 5))
    my_exports = json.loads(request.GET.get('my_exports'))
    (exports, total) = helper.get_exports_page(page, limit, my_exports=my_exports)
    return json_response({
        'exports': exports,
        'total': total,
    })


@location_safe
@login_and_domain_required
@require_GET
def get_saved_export_progress(request, domain):
    permissions = ExportsPermissionsManager(request.GET.get('model_type'), domain, request.couch_user)
    permissions.access_list_exports_or_404(is_deid=json.loads(request.GET.get('is_deid')))

    export_instance_id = request.GET.get('export_instance_id')
    return json_response({
        'taskStatus': _get_task_status_json(export_instance_id),
    })


@location_safe
@login_and_domain_required
@require_POST
def toggle_saved_export_enabled(request, domain):
    permissions = ExportsPermissionsManager(request.GET.get('model_type'), domain, request.couch_user)
    permissions.access_list_exports_or_404(is_deid=json.loads(request.POST.get('is_deid')))

    export_instance_id = request.POST.get('export_id')
    export_instance = get_properly_wrapped_export_instance(export_instance_id)
    export_instance.auto_rebuild_enabled = not json.loads(request.POST.get('is_auto_rebuild_enabled'))
    export_instance.save()
    return json_response({
        'success': True,
        'isAutoRebuildEnabled': export_instance.auto_rebuild_enabled
    })


@location_safe
@login_and_domain_required
@require_POST
def update_emailed_export_data(request, domain):

    permissions = ExportsPermissionsManager(request.GET.get('model_type'), domain, request.couch_user)
    permissions.access_list_exports_or_404(is_deid=json.loads(request.POST.get('is_deid')))

    export_instance_id = request.POST.get('export_id')
    try:
        rebuild_saved_export(export_instance_id, manual=True)
    except XlsLengthException:
        return json_response({
            'error': _('This file has more than 256 columns, which is not supported by xls. '
                       'Please change the output type to csv or xlsx in the export configuration page '
                       'to export this file.')
        })
    return json_response({'success': True})


@location_safe
class DailySavedExportListView(BaseExportListView, DailySavedExportListHelper):
    urlname = 'list_daily_saved_exports'
    page_title = gettext_lazy("Daily Saved Exports")

    def dispatch(self, *args, **kwargs):
        if not self._priv_check():
            raise Http404
        return super(DailySavedExportListView, self).dispatch(*args, **kwargs)

    @property
    def page_context(self):
        context = super(DailySavedExportListView, self).page_context
        model_type = None
        if self.permissions.has_form_export_permissions and not self.permissions.has_case_export_permissions:
            model_type = "form"
        if not self.permissions.has_form_export_permissions and self.permissions.has_case_export_permissions:
            model_type = "case"
        context.update({
            "is_daily_saved_export": True,
            "model_type": model_type,
            "static_model_type": False,
        })
        return context


@require_POST
@location_safe
@login_and_domain_required
def commit_filters(request, domain):
    permissions = ExportsPermissionsManager(request.POST.get('model_type'), domain, request.couch_user)
    if not permissions.has_edit_permissions:
        raise Http404
    export_id = request.POST.get('export_id')
    form_data = json.loads(request.POST.get('form_data'))
    export = get_properly_wrapped_export_instance(export_id)
    if export.is_daily_saved_export and not domain_has_privilege(domain, DAILY_SAVED_EXPORT):
        raise Http404
    if export.export_format == "html" and not domain_has_privilege(domain, EXCEL_DASHBOARD):
        raise Http404
    if export.is_odata_config and not domain_has_privilege(domain, ODATA_FEED):
        raise Http404
    if not export.filters.is_location_safe_for_user(request):
        return location_restricted_response(request)
    domain_object = Domain.get_by_name(domain)
    filter_form = DashboardFeedFilterForm(
        domain_object,
        form_data,
        couch_user=request.couch_user
    )
    if filter_form.is_valid():
        old_can_access_all_locations = export.filters.can_access_all_locations
        old_accessible_location_ids = export.filters.accessible_location_ids
        filters = filter_form.to_export_instance_filters(
            # using existing location restrictions prevents a less restricted user from modifying
            # restrictions on an export that a more restricted user created (which would mean the more
            # restricted user would lose access to the export)
            old_can_access_all_locations,
            old_accessible_location_ids,
            export.type
        )
        if export.filters != filters:
            export.filters = filters
            export.save()
            if export.is_daily_saved_export:
                rebuild_saved_export(export_id, manual=True)
        return json_response({
            'success': True,
            'locationRestrictions': ExportListHelper.get_location_restriction_names(
                export.filters.accessible_location_ids
            ),
        })
    else:
        return json_response({
            'success': False,
            'error': _("Problem saving dashboard feed filters: Invalid form"),
        })


@location_safe
class FormExportListView(BaseExportListView, FormExportListHelper):
    urlname = 'list_form_exports'
    page_title = gettext_noop("Export Form Data")


@location_safe
class CaseExportListView(BaseExportListView, CaseExportListHelper):
    urlname = 'list_case_exports'
    page_title = gettext_noop("Export Case Data")

    @property
    def page_name(self):
        if self.is_deid:
            return _("Export De-Identified Cases")
        return self.page_title

    @method_decorator(login_and_domain_required)
    def dispatch(self, request, *args, **kwargs):
        bulk_export_progress = cache.get(f'{BULK_CASE_EXPORT_CACHE}:{request.domain}')
        if bulk_export_progress:
            messages.info(
                request,
                format_html(
                    _("Populating tables for <strong>{}</strong>. ({}%)"),
                    bulk_export_progress['table_name'],
                    bulk_export_progress['progress']
                )
            )

        return super(CaseExportListView, self).dispatch(request, *args, **kwargs)


@location_safe
class DashboardFeedListView(DailySavedExportListView, DashboardFeedListHelper):
    urlname = 'list_dashboard_feeds'
    page_title = gettext_lazy("Excel Dashboard Integration")

    lead_text = gettext_lazy('''
        Excel dashboard feeds allow Excel to directly connect to CommCare HQ to download data.
        Data is updated daily.
    ''')

    @property
    def page_context(self):
        context = super(DashboardFeedListView, self).page_context
        context.update({
            "is_feed": True,
            "export_type_caps": _("Dashboard Feed"),
            "export_type": _("dashboard feed"),
            "export_type_caps_plural": _("Dashboard Feeds"),
            "export_type_plural": _("dashboard feeds"),
            'my_export_type': _('My Dashboard Feeds'),
            'shared_export_type': _('Dashboard Feeds Shared with Me'),
        })
        return context


class DeIdFormExportListView(FormExportListView, DeIdFormExportListHelper):
    page_title = gettext_noop("Export De-Identified Form Data")
    urlname = 'list_form_deid_exports'


@location_safe
class DeIdDailySavedExportListView(DailySavedExportListView, DeIdDailySavedExportListHelper):
    urlname = 'list_deid_daily_saved_exports'
    page_title = gettext_noop("Export De-Identified Daily Saved Exports")


@location_safe
class DeIdDashboardFeedListView(DashboardFeedListView, DeIdDashboardFeedListHelper):
    urlname = 'list_deid_dashboard_feeds'
    page_title = gettext_noop("Export De-Identified Dashboard Feeds")


def can_download_daily_saved_export(export, domain, couch_user):
    if (export.is_deidentified and user_can_view_deid_exports(domain, couch_user)):
        return True
    elif export.type == FORM_EXPORT and has_permission_to_view_report(
            couch_user, domain, FORM_EXPORT_PERMISSION):
        return True
    elif export.type == CASE_EXPORT and has_permission_to_view_report(
            couch_user, domain, CASE_EXPORT_PERMISSION):
        return True
    return False


@location_safe
@csrf_exempt
@api_auth()
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
                rebuild_saved_export(export_instance_id, manual=False)
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
    format = Format.from_format(export_instance.export_format)
    return get_download_response(payload, export_instance.file_size, format.mimetype,
                                 format.download, export_instance.filename, req)


@require_GET
@login_and_domain_required
@location_safe
def get_app_data_drilldown_values(request, domain):
    if json.loads(request.GET.get('is_deid')):
        raise Http404()

    model_type = request.GET.get('model_type')
    is_odata = json.loads(request.GET.get('is_odata'))
    permissions = ExportsPermissionsManager(model_type, domain, request.couch_user)
    permissions.access_list_exports_or_404(is_deid=False, is_odata=is_odata)

    rmi_helper = ApplicationDataRMIHelper(domain, request.couch_user)
    if model_type == 'form':
        response = rmi_helper.get_form_rmi_response()
    elif model_type == 'case':
        response = rmi_helper.get_case_rmi_response(include_any_app=True)
    else:
        response = rmi_helper.get_dual_model_rmi_response()

    return json_response(response)


@require_POST
@login_and_domain_required
@location_safe
def submit_app_data_drilldown_form(request, domain):
    if json.loads(request.POST.get('is_deid')):
        raise Http404()

    model_type = request.POST.get('model_type')
    is_odata = json.loads(request.POST.get('is_odata'))
    permissions = ExportsPermissionsManager(model_type, domain, request.couch_user)
    permissions.access_list_exports_or_404(is_deid=False, is_odata=is_odata)

    form_data = json.loads(request.POST.get('form_data'))
    is_daily_saved_export = json.loads(request.POST.get('is_daily_saved_export'))
    is_feed = json.loads(request.POST.get('is_feed'))
    is_odata = json.loads(request.POST.get('is_odata'))

    create_form = CreateExportTagForm(
        is_odata or permissions.has_form_export_permissions,
        is_odata or permissions.has_case_export_permissions,
        form_data
    )
    if not create_form.is_valid():
        return json_response({
            'success': False,
            'error': _("The form did not validate."),
        })

    from corehq.apps.export.views.new import (
        CreateNewCaseFeedView,
        CreateNewCustomCaseExportView,
        CreateNewCustomFormExportView,
        CreateNewDailySavedCaseExport,
        CreateNewDailySavedFormExport,
        CreateNewFormFeedView,
        CreateODataCaseFeedView,
        CreateODataFormFeedView,
    )

    if is_odata:
        if create_form.cleaned_data['model_type'] == "case":
            export_tag = create_form.cleaned_data['case_type']
            cls = CreateODataCaseFeedView
        else:
            export_tag = create_form.cleaned_data['form']
            cls = CreateODataFormFeedView
    elif is_daily_saved_export:
        if create_form.cleaned_data['model_type'] == "case":
            export_tag = create_form.cleaned_data['case_type']
            cls = CreateNewCaseFeedView if is_feed else CreateNewDailySavedCaseExport
        else:
            export_tag = create_form.cleaned_data['form']
            cls = CreateNewFormFeedView if is_feed else CreateNewDailySavedFormExport
    elif model_type == 'form':
        export_tag = create_form.cleaned_data['form']
        cls = CreateNewCustomFormExportView
    elif model_type == 'case':
        export_tag = create_form.cleaned_data['case_type']
        cls = CreateNewCustomCaseExportView

    url_params = '?export_tag="{}"'.format(export_tag)
    app_id = create_form.cleaned_data['application']
    if app_id not in [ApplicationDataRMIHelper.UNKNOWN_SOURCE, ApplicationDataRMIHelper.ALL_SOURCES]:
        url_params += '&app_id={}'.format(app_id)

    return json_response({
        'success': True,
        'url': reverse(cls.urlname, args=[domain]) + url_params,
    })


class ODataFeedListHelper(ExportListHelper):
    allow_bulk_export = False
    form_or_case = None
    is_deid = False
    include_saved_filters = True

    @property
    @memoized
    def has_form_export_permissions(self):
        return has_permission_to_view_report(self.request.couch_user, self.domain, FORM_EXPORT_PERMISSION)

    @property
    @memoized
    def has_case_export_permissions(self):
        return has_permission_to_view_report(self.request.couch_user, self.domain, CASE_EXPORT_PERMISSION)

    @property
    @memoized
    def allowed_doc_type(self):
        if self.has_case_export_permissions and self.has_form_export_permissions:
            return None  # get_brief_deid_exports / get_brief_exports interprets this as both
        if self.has_form_export_permissions:
            return FORM_EXPORT
        if self.has_case_export_permissions:
            return CASE_EXPORT
        if user_can_view_deid_exports(self.domain, self.request.couch_user):
            return 'deid'
        return 'neither'

    @memoized
    def get_saved_exports(self):
        if self.allowed_doc_type == 'neither':
            return []

        if self.allowed_doc_type == 'deid':
            exports = get_brief_deid_exports(self.domain, None)
        else:
            exports = get_brief_exports(self.domain, self.allowed_doc_type)
        return [x for x in exports if self._should_appear_in_list(x)]

    @property
    def create_export_form(self):
        form = CreateExportTagForm(True, True)
        form.fields['model_type'].label = _("Feed Type")

        model_type_choices = [
            ('', _("Select field type")),
        ]
        if self.has_case_export_permissions:
            model_type_choices.append(('case', _('Case')))
        if self.has_form_export_permissions:
            model_type_choices.append(('form', _('Form')))
        form.fields['model_type'].choices = model_type_choices

        return form

    @property
    @memoized
    def odata_feed_limit(self):
        domain_object = Domain.get_by_name(self.domain)
        return domain_object.get_odata_feed_limit()

    @property
    def create_export_form_title(self):
        return _("Select Feed Type")

    def _should_appear_in_list(self, export):
        return export['is_odata_config']

    def fmt_export_data(self, export):
        data = super(ODataFeedListHelper, self).fmt_export_data(export)
        data.update({
            'isOData': True,
        })
        if len(self.get_saved_exports()) >= self.odata_feed_limit:
            data['editUrl'] = '#odataFeedLimitReachedModal'
        return data

    def _edit_view(self, export):
        from corehq.apps.export.views.edit import EditODataCaseFeedView, EditODataFormFeedView
        if isinstance(export, FormExportInstance):
            return EditODataFormFeedView
        return EditODataCaseFeedView

    def _download_view(self, export):
        # This isn't actually exposed in the UI
        from corehq.apps.export.views.download import DownloadNewCaseExportView, DownloadNewFormExportView
        if isinstance(export, FormExportInstance):
            return DownloadNewFormExportView
        return DownloadNewCaseExportView


@location_safe
@method_decorator(requires_privilege_with_fallback(ODATA_FEED), name='dispatch')
class ODataFeedListView(BaseExportListView, ODataFeedListHelper):
    is_odata = True
    urlname = 'list_odata_feeds'
    page_title = gettext_lazy("PowerBi/Tableau Integration")

    @property
    def lead_text(self):
        return format_html(_("""
        Use OData feeds to integrate your CommCare data with Power BI or Tableau.
        <a href="https://confluence.dimagi.com/pages/viewpage.action?pageId=63013347"
           id="js-odata-track-learn-more"
           target="_blank">
            Learn more.
        </a><br />
        This feature allows {odata_feed_limit} feed configurations. Need more?
        Please write to us at <a href="mailto:{sales_email}">{sales_email}</a>.
        """),
            odata_feed_limit=self.odata_feed_limit,
            sales_email=settings.SALES_EMAIL,)

    @property
    def page_context(self):
        context = super(ODataFeedListView, self).page_context
        context.update({
            "export_type_caps": _("OData Feed"),
            "export_type": _("OData feed"),
            "export_type_caps_plural": _("OData Feeds"),
            "export_type_plural": _("OData feeds"),
            'my_export_type': _('My OData Feeds'),
            'shared_export_type': _('OData Feeds Shared with Me'),
            'odata_feed_limit': self.odata_feed_limit,
        })
        if len(self.get_saved_exports()) >= self.odata_feed_limit:
            context['create_url'] = '#odataFeedLimitReachedModal'
            context['odata_feeds_over_limit'] = True
        return context


@location_safe
@method_decorator(toggles.SUPERSET_ANALYTICS.required_decorator(), name='dispatch')
class CommCareAnalyticsListView(BaseProjectDataView):
    urlname = 'commcare_analytics'
    page_title = gettext_lazy("CommCare Analytics")
    template_name = 'export/commcare_analytics.html'

    @property
    def page_context(self):
        return {
            "analytics_redirect_url": settings.COMMCARE_ANALYTICS_HOST
        }
