from __future__ import absolute_import

from __future__ import division
from __future__ import unicode_literals
from datetime import datetime, timedelta
import json

from couchdbkit import ResourceNotFound
from django.conf import settings
from django.contrib.humanize.templatetags.humanize import naturaltime
from django.urls import reverse
from django.http import HttpResponseRedirect, HttpResponseBadRequest, Http404, HttpResponse, \
    HttpResponseServerError
from django.template.defaultfilters import filesizeformat
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from corehq.util.download import get_download_response
from corehq.apps.domain.models import Domain
from corehq.apps.export.views.utils import ExportsPermissionsManager, user_can_view_deid_exports
from corehq.apps.hqwebapp.views import HQJSONResponseMixin
from corehq.apps.hqwebapp.utils import format_angular_error, format_angular_success
from corehq.apps.locations.models import SQLLocation
from corehq.apps.locations.permissions import location_safe, location_restricted_response
from corehq.apps.reports.views import should_update_export
from corehq.privileges import EXCEL_DASHBOARD, DAILY_SAVED_EXPORT
from django.utils.decorators import method_decorator


from djangular.views.mixins import allow_remote_invocation
from corehq import toggles
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.app_manager.fields import ApplicationDataRMIHelper
from corehq.apps.domain.decorators import login_and_domain_required, api_auth
from corehq.apps.export.tasks import (
    generate_schema_for_all_builds,
    get_saved_export_task_status,
    rebuild_saved_export,
)
from corehq.apps.export.exceptions import (
    ExportAppException,
    BadExportConfiguration,
    ExportFormValidationException,
)
from corehq.apps.export.forms import (
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
    SharingOption,
    UNKNOWN_EXPORT_OWNER,
)
from corehq.apps.export.dbaccessors import (
    get_form_export_instances,
    get_properly_wrapped_export_instance,
    get_case_exports_by_domain,
    get_form_exports_by_domain,
)
from corehq.apps.reports.models import HQGroupExportConfiguration
from corehq.apps.settings.views import BaseProjectDataView
from corehq.apps.hqwebapp.decorators import (
    use_select2,
    use_daterangepicker,
    use_jquery_ui,
    use_ko_validation,
)
from corehq.apps.users.models import WebUser
from corehq.apps.users.permissions import (
    can_download_data_files,
    CASE_EXPORT_PERMISSION,
    DEID_EXPORT_PERMISSION,
    FORM_EXPORT_PERMISSION,
    has_permission_to_view_report,
)
from corehq.apps.analytics.tasks import track_workflow
from couchexport.models import Format
from memoized import memoized
from django.utils.translation import ugettext as _, ugettext_noop, ugettext_lazy
from dimagi.utils.logging import notify_exception
from dimagi.utils.couch import CriticalSection
from dimagi.utils.web import json_response
from six.moves import map


class BaseExportListView(HQJSONResponseMixin, BaseProjectDataView):
    template_name = 'export/export_list.html'
    allow_bulk_export = True
    is_deid = False

    lead_text = ugettext_lazy('''
        Exports are a way to download data in a variety of formats (CSV, Excel, etc.)
        for use in third-party data analysis tools.
    ''')

    @use_select2
    @use_ko_validation
    @method_decorator(login_and_domain_required)
    def dispatch(self, request, *args, **kwargs):
        self.permissions = ExportsPermissionsManager(self.form_or_case, request.domain, request.couch_user)
        self.permissions.access_list_exports_or_404(is_deid=self.is_deid)

        return super(BaseExportListView, self).dispatch(request, *args, **kwargs)

    @property
    def page_context(self):
        return {
            'exports': self.get_exports_list(),
            'create_export_form': self.create_export_form if not self.is_deid else None,
            'create_export_form_title': self.create_export_form_title if not self.is_deid else None,
            'bulk_download_url': self.bulk_download_url,
            'allow_bulk_export': self.allow_bulk_export,
            'has_edit_permissions': self.permissions.has_edit_permissions,
            'is_deid': self.is_deid,
            "export_type_caps": _("Export"),
            "export_type": _("export"),
            "export_type_caps_plural": _("Exports"),
            "export_type_plural": _("exports"),
            'my_export_type': _('My Exports'),
            'shared_export_type': _('Exports Shared with Me'),
            "model_type": self.form_or_case,
            "static_model_type": True,
            'max_exportable_rows': MAX_EXPORTABLE_ROWS,
            'lead_text': self.lead_text,
        }

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

    def _get_daily_saved_export_metadata(self, export):
        """
        Return a dictionary containing details about an emailed export.
        This will eventually be passed to javascript.
        """

        has_file = export.has_file()
        file_data = {}
        if has_file:
            download_url = self.request.build_absolute_uri(
                reverse('download_daily_saved_export', args=[self.domain, export._id]))
            file_data = self._fmt_emailed_export_fileData(
                export._id, export.file_size, export.last_updated,
                export.last_accessed, download_url
            )

        location_restrictions = []
        locations = []
        filters = export.filters
        if filters.accessible_location_ids:
            locations = SQLLocation.objects.filter(location_id__in=filters.accessible_location_ids)
        for location in locations:
            location_restrictions.append(location.display_name)

        return {
            'groupId': None,  # This can be removed when we're off legacy exports
            'hasFile': has_file,
            'index': None,  # This can be removed when we're off legacy exports
            'fileData': file_data,
            'filters': DashboardFeedFilterForm.get_form_data_from_export_instance_filters(
                filters, self.domain, type(export)
            ),
            'isLocationSafeForUser': filters.is_location_safe_for_user(self.request),
            'locationRestrictions': location_restrictions,
            'taskStatus': _get_task_status_json(export._id),
            'updatingData': False,
        }

    def _fmt_emailed_export_fileData(self, fileId, size, last_updated,
                                     last_accessed, download_url):
        """
        Return a dictionary containing details about an emailed export file.
        This will eventually be passed to an Angular controller.
        """
        return {
            'fileId': fileId,
            'size': filesizeformat(size),
            'lastUpdated': naturaltime(last_updated),
            'lastAccessed': naturaltime(last_accessed),
            'showExpiredWarning': (
                last_accessed and
                last_accessed <
                (datetime.utcnow() - timedelta(days=settings.SAVED_EXPORT_ACCESS_CUTOFF))
            ),
            'downloadUrl': download_url,
        }

    def get_exports_list(self):
        # Calls self.get_saved_exports and formats each item using self.fmt_export_data
        saved_exports = self.get_saved_exports()
        if toggles.EXPORT_OWNERSHIP.enabled(self.request.domain):
            saved_exports = [
                export for export in saved_exports
                if export.can_view(self.request.couch_user.user_id)
            ]
        if self.is_deid:
            saved_exports = [x for x in saved_exports if x.is_safe]
        return list(map(self.fmt_export_data, saved_exports))

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


def _get_task_status_json(export_instance_id):
    status = get_saved_export_task_status(export_instance_id)
    return {
        'percentComplete': status.progress.percent or 0,
        'inProgress': status.started(),
        'success': status.success(),
        'justFinished': False,
    }


@login_and_domain_required
@require_GET
def get_saved_export_progress(request, domain):
    permissions = ExportsPermissionsManager(request.GET.get('model_type'), domain, request.couch_user)
    permissions.access_list_exports_or_404(is_deid=request.GET.get('is_deid'))

    export_instance_id = request.GET.get('export_instance_id')
    return json_response({
        'taskStatus': _get_task_status_json(export_instance_id),
    })


@login_and_domain_required
@require_POST
def toggle_saved_export_enabled(request, domain):
    permissions = ExportsPermissionsManager(request.GET.get('model_type'), domain, request.couch_user)
    permissions.access_list_exports_or_404(is_deid=request.GET.get('is_deid'))

    export_instance_id = request.POST.get('export_id')
    export_instance = get_properly_wrapped_export_instance(export_instance_id)
    export_instance.auto_rebuild_enabled = not json.loads(request.POST.get('is_auto_rebuild_enabled'))
    export_instance.save()
    return json_response({
        'success': True,
        'isAutoRebuildEnabled': export_instance.auto_rebuild_enabled
    })


@login_and_domain_required
@require_POST
def update_emailed_export_data(request, domain):
    permissions = ExportsPermissionsManager(request.GET.get('model_type'), domain, request.couch_user)
    permissions.access_list_exports_or_404(is_deid=request.GET.get('is_deid'))

    export_instance_id = request.POST.get('export_id')
    rebuild_saved_export(export_instance_id, manual=True)
    return json_response({'success': True})


@location_safe
class DailySavedExportListView(BaseExportListView):
    urlname = 'list_daily_saved_exports'
    page_title = ugettext_lazy("Daily Saved Exports")
    form_or_case = None  # This view lists both case and form feeds
    allow_bulk_export = False

    def dispatch(self, *args, **kwargs):
        if not self._priv_check():
            raise Http404
        return super(DailySavedExportListView, self).dispatch(*args, **kwargs)

    def _priv_check(self):
        return domain_has_privilege(self.domain, DAILY_SAVED_EXPORT)

    def _get_edit_export_class(self, model):
        from corehq.apps.export.views.edit import EditFormDailySavedExportView, EditCaseDailySavedExportView
        return {
            "form": EditFormDailySavedExportView,
            "case": EditCaseDailySavedExportView
        }[model]

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
            "export_filter_form": DashboardFeedFilterForm(
                self.domain_object,
            )
        })
        return context

    @property
    @memoized
    def create_export_form_title(self):
        return "Select a model to export"  # could be form or case

    @property
    def bulk_download_url(self):
        # Daily Saved exports do not support bulk download
        return ""

    @memoized
    def get_saved_exports(self):
        combined_exports = []
        if self.permissions.has_form_export_permissions:
            combined_exports.extend(get_form_exports_by_domain(self.domain,
                                                               self.permissions.has_deid_view_permissions))
        if self.permissions.has_case_export_permissions:
            combined_exports.extend(get_case_exports_by_domain(self.domain,
                                                               self.permissions.has_deid_view_permissions))
        combined_exports = sorted(combined_exports, key=lambda x: x.name)
        return [x for x in combined_exports if x.is_daily_saved_export and not x.export_format == "html"]

    @property
    def daily_emailed_exports(self):
        # This function only returns old-style exports. Since this view will only be visible for people using new
        # exports, it need not return anything.
        return []

    def fmt_export_data(self, export):
        from corehq.apps.export.views.new import CopyExportView
        from corehq.apps.export.views.download import DownloadNewCaseExportView, DownloadNewFormExportView
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
            'name': export.name,
            'description': export.description,
            'lastBuildDuration': (str(timedelta(milliseconds=export.last_build_duration))
                                  if export.last_build_duration else ''),
            'my_export': export.owner_id == self.request.couch_user.user_id,
            'sharing': export.sharing,
            'owner_username': (
                WebUser.get_by_user_id(export.owner_id).username
                if export.owner_id else UNKNOWN_EXPORT_OWNER
            ),
            'can_edit': export.can_edit(self.request.couch_user),
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


@require_POST
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
    if not export.filters.is_location_safe_for_user(request):
        return location_restricted_response(request)
    domain_object = Domain.get_by_name(domain)
    filter_form = DashboardFeedFilterForm(domain_object, form_data)
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
            rebuild_saved_export(export_id, manual=True)
        return json_response({
            'success': True,
        })
    else:
        return json_response({
            'success': False,
            'error': _("Problem saving dashboard feed filters: Invalid form"),
        })


@location_safe
class FormExportListView(BaseExportListView):
    urlname = 'list_form_exports'
    page_title = ugettext_noop("Export Form Data")
    form_or_case = 'form'

    @property
    def bulk_download_url(self):
        from corehq.apps.export.views.download import BulkDownloadNewFormExportView
        return reverse(BulkDownloadNewFormExportView.urlname, args=(self.domain,))

    @memoized
    def get_saved_exports(self):
        exports = get_form_exports_by_domain(self.domain, self.permissions.has_deid_view_permissions)
        # New exports display daily saved exports in their own view
        return [x for x in exports if not x.is_daily_saved_export]

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
        from corehq.apps.export.views.new import CopyExportView
        from corehq.apps.export.views.edit import EditNewCustomFormExportView
        emailed_export = None
        if export.is_daily_saved_export:
            emailed_export = self._get_daily_saved_export_metadata(export)
        owner_username = (
            WebUser.get_by_user_id(export.owner_id).username
            if export.owner_id else UNKNOWN_EXPORT_OWNER
        )

        return {
            'id': export.get_id,
            'isDeid': export.is_safe,
            'name': export.name,
            'description': export.description,
            'lastBuildDuration': '',
            'my_export': export.owner_id == self.request.couch_user.user_id,
            'sharing': export.sharing,
            'owner_username': owner_username,
            'can_edit': export.can_edit(self.request.couch_user),
            'formname': export.formname,
            'addedToBulk': False,
            'exportType': export.type,
            'emailedExport': emailed_export,
            'editUrl': reverse(EditNewCustomFormExportView.urlname,
                               args=(self.domain, export.get_id)),
            'downloadUrl': self._get_download_url(export.get_id),
            'copyUrl': reverse(CopyExportView.urlname, args=(self.domain, export.get_id)),
        }

    def _get_download_url(self, export_id):
        from corehq.apps.export.views.download import DownloadNewFormExportView
        return reverse(DownloadNewFormExportView.urlname, args=(self.domain, export_id))


@location_safe
class CaseExportListView(BaseExportListView):
    urlname = 'list_case_exports'
    page_title = ugettext_noop("Export Case Data")
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
        exports = get_case_exports_by_domain(self.domain, self.permissions.has_deid_view_permissions)
        return [x for x in exports if not x.is_daily_saved_export]

    @property
    def create_export_form_title(self):
        return _("Select a Case Type to Export")

    def fmt_export_data(self, export):
        from corehq.apps.export.views.edit import EditNewCustomCaseExportView
        from corehq.apps.export.views.new import CopyExportView
        emailed_export = None
        if export.is_daily_saved_export:
            emailed_export = self._get_daily_saved_export_metadata(export)
        owner_username = (
            WebUser.get_by_user_id(export.owner_id).username
            if export.owner_id else UNKNOWN_EXPORT_OWNER
        )

        return {
            'id': export.get_id,
            'isDeid': export.is_safe,
            'name': export.name,
            'case_type': export.case_type,
            'description': export.description,
            'lastBuildDuration': '',
            'my_export': export.owner_id == self.request.couch_user.user_id,
            'sharing': export.sharing,
            'owner_username': owner_username,
            'can_edit': export.can_edit(self.request.couch_user),
            'addedToBulk': False,
            'exportType': export.type,
            'emailedExport': emailed_export,
            'editUrl': reverse(EditNewCustomCaseExportView.urlname, args=(self.domain, export.get_id)),
            'downloadUrl': self._get_download_url(export._id),
            'copyUrl': reverse(CopyExportView.urlname, args=(self.domain, export.get_id)),
        }

    def _get_download_url(self, export_id):
        from corehq.apps.export.views.download import DownloadNewCaseExportView
        return reverse(DownloadNewCaseExportView.urlname, args=(self.domain, export_id))


@location_safe
class DashboardFeedListView(DailySavedExportListView):
    urlname = 'list_dashboard_feeds'
    page_title = ugettext_lazy("Excel Dashboard Integration")
    form_or_case = None  # This view lists both case and form feeds
    allow_bulk_export = False

    lead_text = ugettext_lazy('''
        Excel dashboard feeds allow Excel to directly connect to CommCareHQ to download data.
        Data is updated daily.
    ''')

    def _priv_check(self):
        return domain_has_privilege(self.domain, EXCEL_DASHBOARD)

    def _get_edit_export_class(self, model):
        from corehq.apps.export.views.edit import EditFormFeedView, EditCaseFeedView
        return {
            "form": EditFormFeedView,
            "case": EditCaseFeedView
        }[model]

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

    def fmt_export_data(self, export):
        data = super(DashboardFeedListView, self).fmt_export_data(export)
        data.update({
            'isFeed': True,
        })
        return data

    @memoized
    def get_saved_exports(self):
        combined_exports = []
        if self.permissions.has_form_export_permissions:
            combined_exports.extend(get_form_exports_by_domain(self.domain,
                                                               self.permissions.has_deid_view_permissions))
        if self.permissions.has_case_export_permissions:
            combined_exports.extend(get_case_exports_by_domain(self.domain,
                                                               self.permissions.has_deid_view_permissions))
        combined_exports = sorted(combined_exports, key=lambda x: x.name)
        return [x for x in combined_exports if x.is_daily_saved_export and x.export_format == "html"]


class DeIdFormExportListView(FormExportListView):
    page_title = ugettext_noop("Export De-Identified Form Data")
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
    return get_download_response(payload, export_instance.file_size, format, export_instance.filename, req)


@require_GET
@login_and_domain_required
def get_app_data_drilldown_values(request, domain):
    if json.loads(request.GET.get('is_deid')):
        raise Http404()

    model_type = request.GET.get('model_type')
    permissions = ExportsPermissionsManager(model_type, domain, request.couch_user)
    permissions.access_list_exports_or_404(is_deid=False)

    rmi_helper = ApplicationDataRMIHelper(domain, request.couch_user)
    if model_type == 'form':
        response = rmi_helper.get_form_rmi_response()
    elif model_type == 'case':
        response = rmi_helper.get_case_rmi_response()
    else:
        response = rmi_helper.get_dual_model_rmi_response()

    return json_response(response)


@require_POST
@login_and_domain_required
def submit_app_data_drilldown_form(request, domain):
    if json.loads(request.POST.get('is_deid')):
        raise Http404()

    model_type = request.POST.get('model_type')
    permissions = ExportsPermissionsManager(model_type, domain, request.couch_user)
    permissions.access_list_exports_or_404(is_deid=False)

    form_data = json.loads(request.POST.get('form_data'))
    is_daily_saved_export = json.loads(request.POST.get('is_daily_saved_export'))
    is_feed = json.loads(request.POST.get('is_feed'))

    create_form = CreateExportTagForm(
        permissions.has_form_export_permissions,
        permissions.has_case_export_permissions,
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
    )

    if is_daily_saved_export:
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
    if app_id != ApplicationDataRMIHelper.UNKNOWN_SOURCE:
        url_params += '&app_id={}'.format(app_id)

    return json_response({
        'success': True,
        'url': reverse(cls.urlname, args=[domain]) + url_params,
    })
