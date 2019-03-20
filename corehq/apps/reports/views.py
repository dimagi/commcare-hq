from __future__ import absolute_import, unicode_literals
from collections import OrderedDict
import copy
from datetime import datetime, timedelta, date
from functools import partial
import itertools
import json
import csv342 as csv

from corehq.util.download import get_download_response
from dimagi.utils.couch import CriticalSection
from corehq.apps.reports.tasks import send_email_report
from corehq.apps.app_manager.suite_xml.sections.entries import EntriesHelper
from corehq.apps.cloudcare import CLOUDCARE_DEVICE_ID
from corehq.apps.domain.views.base import BaseDomainView
from corehq.apps.hqwebapp.doc_info import get_doc_info_by_id, DocInfo
from corehq.apps.hqwebapp.templatetags.hq_shared_tags import toggle_enabled
from corehq.apps.hqwebapp.view_permissions import user_can_view_reports
from corehq.apps.locations.permissions import conditionally_location_safe, \
    report_class_is_location_safe
from corehq.apps.receiverwrapper.auth import AuthContext
from corehq.apps.reports.display import xmlns_to_name
from corehq.apps.reports.formdetails.readable import get_readable_data_for_submission, get_data_cleaning_data
from corehq.apps.users.permissions import FORM_EXPORT_PERMISSION, CASE_EXPORT_PERMISSION, \
    DEID_EXPORT_PERMISSION
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors, FormAccessors, LedgerAccessors
from corehq.form_processor.utils.general import use_sqlite_backend
from corehq.form_processor.interfaces.processor import FormProcessorInterface
from corehq.motech.repeaters.dbaccessors import get_repeat_records_by_payload_id
from corehq.apps.reports.view_helpers import case_hierarchy_context
from corehq.tabs.tabclasses import ProjectReportsTab
from corehq.util.timezones.conversions import ServerTime
from corehq.util.timezones.utils import get_timezone_for_request
import langcodes
import pytz
import re
import io
from six.moves import zip

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.base import ContentFile
from django.http import (
    Http404,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseForbidden,
    HttpResponseNotFound,
    HttpResponseRedirect,
    JsonResponse,
)
from django.shortcuts import render
from django.template.loader import render_to_string
from django.utils.decorators import method_decorator
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _, ugettext_lazy, ugettext_noop, get_language
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import (
    require_GET,
    require_http_methods,
    require_POST,
)
from django.views.generic import View
from django.views.generic.base import TemplateView

from casexml.apps.case import const
from casexml.apps.case.cleanup import rebuild_case_from_forms, close_case
from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.templatetags.case_tags import case_inline_display
from casexml.apps.case.xform import extract_case_blocks, get_case_updates
from casexml.apps.case.xml import V2
from casexml.apps.case.util import (
    get_case_history,
    get_paged_changes_to_case_property,
)
from casexml.apps.stock.models import StockTransaction
from casexml.apps.case.views import get_wrapped_case
from couchdbkit.exceptions import ResourceNotFound
import couchexport
from corehq.form_processor.exceptions import CaseNotFound
from corehq.form_processor.models import UserRequestedRebuild

from couchexport.exceptions import (
    CouchExportException,
    SchemaMismatchException
)
from couchexport.export import Format, export_from_tables
from couchexport.models import DefaultExportSchema, SavedBasicExport
from couchexport.shortcuts import (export_data_shared, export_raw_data,
                                   export_response)
from couchexport.tasks import rebuild_schemas
from couchexport.util import SerializableFunction
from couchforms.filters import instances

from dimagi.utils.couch.cache.cache_core import get_redis_client
from dimagi.utils.couch.loosechange import parse_date
from dimagi.utils.decorators.datespan import datespan_in_request
from memoized import memoized
from dimagi.utils.logging import notify_exception
from dimagi.utils.parsing import (json_format_datetime, string_to_boolean,
                                  string_to_datetime, json_format_date)
from dimagi.utils.web import json_request, json_response
from django_prbac.utils import has_privilege
from soil import DownloadBase

from corehq import privileges, toggles
from corehq.apps.accounting.decorators import requires_privilege_json_response
from corehq.apps.analytics.tasks import track_workflow
from corehq.apps.app_manager.const import USERCASE_TYPE, USERCASE_ID
from corehq.apps.app_manager.dbaccessors import get_latest_app_ids_and_versions
from corehq.apps.app_manager.models import Application, ShadowForm
from corehq.apps.app_manager.util import get_form_source_download_url
from corehq.apps.cloudcare.const import DEVICE_ID as FORMPLAYER_DEVICE_ID
from corehq.apps.cloudcare.touchforms_api import get_user_contributions_to_touchforms_session
from corehq.apps.domain.decorators import (
    login_and_domain_required,
    login_or_digest,
    api_auth,
)
from corehq.apps.domain.models import Domain, DomainAuditRecordEntry
from corehq.apps.export.custom_export_helpers import make_custom_export_helper
from corehq.apps.export.exceptions import BadExportConfiguration
from corehq.apps.export.models import CaseExportDataSchema
from corehq.apps.export.utils import is_occurrence_deleted
from corehq.apps.reports.exceptions import EditFormValidationError
from corehq.apps.groups.models import Group
from corehq.apps.hqcase.utils import submit_case_blocks, EDIT_FORM_XMLNS
from corehq.apps.locations.permissions import can_edit_form_location, location_safe, \
    location_restricted_exception, user_can_access_case
from corehq.apps.products.models import SQLProduct
from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.apps.userreports.util import default_language as ucr_default_language
from corehq.apps.reports.util import validate_xform_for_edit
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import (
    CommCareUser,
    CouchUser,
    Permissions,
    WebUser,
)
from corehq.util.couch import get_document_or_404
from corehq.util.timezones.utils import get_timezone_for_user
from corehq.util.view_utils import (
    absolute_reverse,
    reverse,
    get_case_or_404,
    get_form_or_404,
    request_as_dict
)

from .dispatcher import ProjectReportDispatcher
from .export import (
    ApplicationBulkExportHelper,
    CustomBulkExportHelper,
)
from .exportfilters import default_form_filter
from .filters.users import UserTypeFilter
from .forms import SavedReportConfigForm
from .models import (
    ReportConfig,
    ReportNotification,
    DefaultFormExportSchema,
    HQGroupExportConfiguration
)

from .standard import inspect, ProjectReport
from .standard.cases.basic import CaseListReport
from .tasks import (
    build_form_multimedia_zip,
    rebuild_export_async,
    send_delayed_report,
)
from .util import (
    create_export_filter,
    get_group,
    group_filter,
    users_matching_filter,
)
from corehq.form_processor.utils.xform import resave_form
from corehq.apps.hqcase.utils import resave_case
from corehq.apps.hqwebapp.decorators import (
    use_jquery_ui,
    use_select2_v4,
    use_datatables,
    use_multiselect,
    use_jquery_ui
)
import six
from six.moves import range
from no_exceptions.exceptions import Http403


# Number of columns in case property history popup
DYNAMIC_CASE_PROPERTIES_COLUMNS = 4


datespan_default = datespan_in_request(
    from_param="startdate",
    to_param="enddate",
    default_days=7,
)

require_form_export_permission = require_permission(
    Permissions.view_report, FORM_EXPORT_PERMISSION, login_decorator=None)
require_form_deid_export_permission = require_permission(
    Permissions.view_report, DEID_EXPORT_PERMISSION, login_decorator=None)
require_case_export_permission = require_permission(
    Permissions.view_report, CASE_EXPORT_PERMISSION, login_decorator=None)

require_form_view_permission = require_permission(Permissions.view_report, 'corehq.apps.reports.standard.inspect.SubmitHistory', login_decorator=None)
require_case_view_permission = require_permission(Permissions.view_report, 'corehq.apps.reports.standard.cases.basic.CaseListReport', login_decorator=None)

require_can_view_all_reports = require_permission(Permissions.view_reports)


def can_view_attachments(request):
    return (
        request.couch_user.has_permission(
            request.domain, 'view_report',
            data='corehq.apps.reports.standard.cases.basic.CaseListReport'
        )
        or toggles.ALLOW_CASE_ATTACHMENTS_VIEW.enabled(request.user.username)
        or toggles.ALLOW_CASE_ATTACHMENTS_VIEW.enabled(request.domain)
    )


class BaseProjectReportSectionView(BaseDomainView):
    section_name = ugettext_lazy("Project Reports")

    def dispatch(self, request, *args, **kwargs):
        request.project = Domain.get_by_name(self.domain)
        if not hasattr(request, 'couch_user'):
            raise Http404()
        if not user_can_view_reports(request.project, request.couch_user):
            raise Http404()
        return super(BaseProjectReportSectionView, self).dispatch(request, *args, **kwargs)

    @property
    def section_url(self):
        return reverse('reports_home', args=(self.domain, ))


@location_safe
class MySavedReportsView(BaseProjectReportSectionView):
    urlname = 'saved_reports'
    page_title = ugettext_noop("My Saved Reports")
    template_name = 'reports/reports_home.html'

    default_scheduled_report_length = 10

    @use_jquery_ui
    @use_datatables
    def dispatch(self, request, *args, **kwargs):
        return super(MySavedReportsView, self).dispatch(request, *args, **kwargs)

    @property
    def language(self):
        return self.request.couch_user.language or ucr_default_language()

    @property
    def good_configs(self):
        all_configs = ReportConfig.by_domain_and_owner(self.domain, self.request.couch_user._id)
        good_configs = []
        for config in all_configs:
            if config.is_configurable_report and not config.configurable_report:
                continue

            good_configs.append(config.to_complete_json(lang=self.language))
        return good_configs

    @property
    def scheduled_reports(self):

        def _is_valid(rn):
            # the _id check is for weird bugs we've seen in the wild that look like
            # oddities in couch.
            return (
                hasattr(rn, "_id")
                and rn._id
                and rn.configs
                and (
                    not hasattr(rn, 'report_slug')
                    or rn.report_slug != 'admin_domains'
                )
            )

        scheduled_reports = [
            r for r in ReportNotification.by_domain_and_owner(
                self.domain, self.request.couch_user._id)
            if _is_valid(r)
        ]
        scheduled_reports = sorted(scheduled_reports,
                                   key=lambda s: s.configs[0].name)
        for report in scheduled_reports:
            self._adjust_report_day_and_time(report)
        return sorted(scheduled_reports, key=self._report_sort_key())

    @property
    def show_all_scheduled_reports(self):
        return self.request.GET.get('show_all_scheduled_reports', False)

    @property
    def others_scheduled_reports(self):
        def _is_valid(rn):
            # the _id check is for weird bugs we've seen in the wild that look like
            # oddities in couch.
            return (
                hasattr(rn, "_id")
                and rn._id
                and rn.configs
                and (
                    not hasattr(rn, 'report_slug')
                    or rn.report_slug != 'admin_domains'
                )
            )

        ret = []
        key = [self.domain]
        all_scheduled_reports = ReportNotification.view('reportconfig/user_notifications', reduce=False,
                                                        include_docs=True, startkey=key, endkey=key + [{}])
        user = self.request.couch_user
        user_email = user.get_email()
        is_admin = user.is_domain_admin(self.domain)
        for scheduled_report in all_scheduled_reports:
            if not _is_valid(scheduled_report) or user_email == scheduled_report.owner_email:
                continue
            self._adjust_report_day_and_time(scheduled_report)
            if is_admin:
                ret.append(scheduled_report)
            elif user_email in scheduled_report.all_recipient_emails:
                ret.append(scheduled_report)
        return sorted(ret, key=self._report_sort_key())

    def _report_sort_key(self):
        return lambda report: report.configs[0].full_name.lower() if report.configs else None

    def _adjust_report_day_and_time(self, report):
        time_difference = get_timezone_difference(self.domain)
        (report.hour, day_change) = recalculate_hour(
            report.hour,
            int(time_difference[:3]),
            int(time_difference[3:])
        )
        report.minute = 0
        if day_change:
            report.day = calculate_day(report.interval, report.day, day_change)
        return report

    @property
    def page_context(self):
        user = self.request.couch_user
        others_scheduled_reports = self.others_scheduled_reports
        if self.show_all_scheduled_reports:
            num_unlisted_scheduled_reports = 0
        else:
            cur_len = len(others_scheduled_reports)
            num_unlisted_scheduled_reports = max(0, cur_len - self.default_scheduled_report_length)
            others_scheduled_reports = others_scheduled_reports[:min(self.default_scheduled_report_length,
                                                                     cur_len)]

        class OthersScheduledReportWrapper(ReportNotification):
            @property
            def context_secret(self):
                return self.get_secret(user.get_email())

        for other_report in others_scheduled_reports:
            other_report.__class__ = OthersScheduledReportWrapper
        return {
            'couch_user': user,
            'user_email': user.get_email(),
            'is_admin': user.is_domain_admin(self.domain),
            'configs': self.good_configs,
            'scheduled_reports': self.scheduled_reports,
            'others_scheduled_reports': others_scheduled_reports,
            'extra_reports': num_unlisted_scheduled_reports,
            'report': {
                'title': self.page_title,
                'show': True,
                'slug': None,
                'is_async': True,
                'section_name': self.section_name,
            }
        }


@requires_privilege_json_response(privileges.API_ACCESS)
@login_or_digest
@require_form_export_permission
@datespan_default
@require_GET
def export_data(req, domain):
    """
    Download all data for a couchdbkit model
    """
    try:
        export_tag = json.loads(req.GET.get("export_tag", "null") or "null")
    except ValueError:
        return HttpResponseBadRequest()

    include_errors = string_to_boolean(req.GET.get("include_errors", False))

    kwargs = {"format": req.GET.get("format", Format.XLS_2007),
              "previous_export_id": req.GET.get("previous_export", None),
              "filename": export_tag,
              "use_cache": string_to_boolean(req.GET.get("use_cache", "True")),
              "max_column_size": int(req.GET.get("max_column_size", 2000)),
              "separator": req.GET.get("separator", "|")}

    user_filter, _ = UserTypeFilter.get_user_filter(req)

    if user_filter:
        filtered_users = users_matching_filter(domain, user_filter)

        def _ufilter(user):
            try:
                return user['form']['meta']['userID'] in filtered_users
            except KeyError:
                return False
        filter = _ufilter
    else:
        group = get_group(**json_request(req.GET))
        filter = SerializableFunction(group_filter, group=group)

    errors_filter = instances if not include_errors else None

    kwargs['filter'] = couchexport.util.intersect_functions(filter, errors_filter)
    if kwargs['format'] == 'raw':
        resp = export_raw_data([domain, export_tag], filename=export_tag)
    else:
        try:
            resp = export_data_shared([domain, export_tag], **kwargs)
        except CouchExportException as e:
            return HttpResponseBadRequest(e)
    if resp:
        return resp
    else:
        messages.error(req, "Sorry, there was no data found for the tag '%s'." % export_tag)
        raise Http404()


@require_form_export_permission
@login_and_domain_required
@datespan_default
@require_GET
def export_data_async(request, domain):
    """
    Download all data for a couchdbkit model
    """
    try:
        export_tag = json.loads(request.GET.get("export_tag", "null") or "null")
        export_type = request.GET.get("type", "form")
    except ValueError:
        return HttpResponseBadRequest()
    assert(export_tag[0] == domain)
    format = request.GET.get("format", Format.XLS_2007)
    filename = request.GET.get("filename", None)
    previous_export_id = request.GET.get("previous_export", None)

    filter = create_export_filter(request, domain, export_type=export_type)

    def _export_tag_or_bust(request):
        export_tag = request.GET.get("export_tag", "")
        if not export_tag:
            raise Exception("You must specify a model to download!")
        try:
            # try to parse this like a compound json list
            export_tag = json.loads(request.GET.get("export_tag", ""))
        except ValueError:
            pass  # assume it was a string
        return export_tag

    export_tag = _export_tag_or_bust(request)
    export_object = DefaultExportSchema(index=export_tag)

    return export_object.export_data_async(
        filter=filter,
        filename=filename,
        previous_export_id=previous_export_id,
        format=format
    )


@login_or_digest
@datespan_default
def export_default_or_custom_data(request, domain, export_id=None, bulk_export=False):
    """
    Export data from a saved export schema
    """
    r = request.POST if request.method == 'POST' else request.GET
    deid = r.get('deid') == 'true'
    if deid:
        return _export_deid(request, domain, export_id, bulk_export=bulk_export)
    else:
        return _export_no_deid(request, domain, export_id, bulk_export=bulk_export)


@require_permission('view_report', DEID_EXPORT_PERMISSION, login_decorator=None)
def _export_deid(request, domain, export_id=None, bulk_export=False):
    return _export_default_or_custom_data(request, domain, export_id, bulk_export=bulk_export, safe_only=True)


@require_form_export_permission
def _export_no_deid(request, domain, export_id=None, bulk_export=False):
    return _export_default_or_custom_data(request, domain, export_id, bulk_export=bulk_export)


def _export_default_or_custom_data(request, domain, export_id=None, bulk_export=False, safe_only=False):
    req = request.POST if request.method == 'POST' else request.GET
    async = req.get('async') == 'true'
    format = req.get("format", "")
    export_type = req.get("type", "form")
    previous_export_id = req.get("previous_export", None)
    filename = req.get("filename", None)
    max_column_size = int(req.get("max_column_size", 2000))
    limit = int(req.get("limit", 0))

    filter = create_export_filter(request, domain, export_type=export_type)
    if bulk_export:
        try:
            is_custom = json.loads(req.get("is_custom", "false"))
            export_tags = json.loads(req.get("export_tags", "null") or "null")
        except ValueError:
            return HttpResponseBadRequest()

        export_helper = (CustomBulkExportHelper if is_custom else ApplicationBulkExportHelper)(
            domain=domain,
            safe_only=safe_only
        )

        if export_type == 'form':
            filter &= SerializableFunction(instances)

        return export_helper.prepare_export(export_tags, filter)

    elif export_id:
        # this is a custom export
        try:
            export_object = make_custom_export_helper(request, export_type, domain, export_id).custom_export
            if safe_only and not export_object.is_safe:
                return HttpResponseForbidden()
        except ResourceNotFound:
            raise Http404()
        except BadExportConfiguration as e:
            return HttpResponseBadRequest(str(e))

    elif safe_only:
        return HttpResponseForbidden()
    else:
        if not async:
            # this function doesn't support synchronous export without a custom export object
            # if we ever want that (i.e. for HTML Preview) then we just need to give
            # FakeSavedExportSchema a download_data function (called below)
            return HttpResponseBadRequest()
        try:
            export_tag = json.loads(req.get("export_tag", "null") or "null")
        except ValueError:
            return HttpResponseBadRequest()
        assert(export_tag[0] == domain)
        # hack - also filter instances here rather than mess too much with trying to make this
        # look more like a FormExportSchema
        export_class = DefaultExportSchema
        if export_type == 'form':
            filter &= SerializableFunction(instances)
            export_class = DefaultFormExportSchema

        export_object = export_class(index=export_tag)

    if export_type == 'form':
        _filter = filter
        filter = SerializableFunction(default_form_filter, filter=_filter)

    if not filename:
        filename = export_object.name
    filename += ' ' + date.today().isoformat()

    if async:
        return export_object.export_data_async(
            filter=filter,
            filename=filename,
            previous_export_id=previous_export_id,
            format=format,
            max_column_size=max_column_size,
        )
    else:
        try:
            resp = export_object.download_data(format, filter=filter, limit=limit)
        except SchemaMismatchException as e:
            rebuild_schemas.delay(export_object.index)
            messages.error(
                request,
                "Sorry, the export failed for %s, please try again later" \
                    % export_object.name
            )
            raise Http404()
        if resp:
            return resp
        else:
            messages.error(request, "Sorry, there was no data found for the tag '%s'." % export_object.name)
            raise Http404()


@csrf_exempt
@api_auth
@require_form_export_permission
@require_GET
def hq_download_saved_export(req, domain, export_id):
    with CriticalSection(['saved-export-{}'.format(export_id)]):
        saved_export = SavedBasicExport.get(export_id)
        return _download_saved_export(req, domain, saved_export)


@csrf_exempt
@api_auth
@require_form_deid_export_permission
@require_GET
def hq_deid_download_saved_export(req, domain, export_id):
    with CriticalSection(['saved-export-{}'.format(export_id)]):
        saved_export = SavedBasicExport.get(export_id)
        if not saved_export.is_safe:
            raise Http404()
        return _download_saved_export(req, domain, saved_export)


def _download_saved_export(req, domain, saved_export):
    if domain != saved_export.configuration.index[0]:
        raise Http404()

    if should_update_export(saved_export.last_accessed):
        group_id = req.GET.get('group_export_id')
        if group_id:
            try:
                group_config = HQGroupExportConfiguration.get(group_id)
                assert domain == group_config.domain
                all_config_indices = [schema.index for schema in group_config.all_configs]
                list_index = all_config_indices.index(saved_export.configuration.index)
                schema = next(itertools.islice(group_config.all_export_schemas,
                                               list_index,
                                               list_index+1))
                rebuild_export_async.delay(saved_export.configuration, schema)
            except Exception:
                notify_exception(req, 'Failed to rebuild export during download')

    saved_export.last_accessed = datetime.utcnow()
    saved_export.save()

    payload = saved_export.get_payload(stream=True)
    format = Format.from_format(saved_export.configuration.format)
    return get_download_response(payload, saved_export.size, format, saved_export.configuration.filename, req)


def should_update_export(last_accessed):
    cutoff = datetime.utcnow() - timedelta(days=settings.SAVED_EXPORT_ACCESS_CUTOFF)
    return not last_accessed or last_accessed < cutoff


def touch_saved_reports_views(user, domain):
    """
    Hit the saved reports views so stale=update_after doesn't cause the user to
    see old or deleted data after a change when they next load the reports
    homepage.

    """
    ReportConfig.by_domain_and_owner(domain, user._id, limit=1, stale=False)
    ReportNotification.by_domain_and_owner(domain, user._id, limit=1, stale=False)


@location_safe
class AddSavedReportConfigView(View):
    name = 'add_report_config'

    @method_decorator(login_and_domain_required)
    def post(self, request, domain, *args, **kwargs):
        self.domain = domain

        if not self.saved_report_config_form.is_valid():
            errors = self.saved_report_config_form.errors.get('__all__', [])
            return HttpResponseBadRequest(', '.join(errors))

        update_config_data = copy.copy(self.saved_report_config_form.cleaned_data)
        del update_config_data['_id']
        update_config_data.update({
            'filters': self.filters,
        })
        for field in self.config.properties().keys():
            if field in update_config_data:
                setattr(self.config, field, update_config_data[field])

        # remove start and end date if the date range is "last xx days" or none
        if self.saved_report_config_form.cleaned_data['date_range'] in [
            'last30',
            'last7',
            'lastn',
            'lastmonth',
            'lastyear',
            None,
        ]:
            if "start_date" in self.config:
                delattr(self.config, "start_date")
            if "end_date" in self.config:
                delattr(self.config, "end_date")
        # remove days if the date range has specific dates
        elif self.saved_report_config_form.cleaned_data['date_range'] in [
            'since',
            'range',
        ]:
            if "days" in self.config:
                delattr(self.config, "days")

        self.config.save()
        ProjectReportsTab.clear_dropdown_cache(self.domain, request.couch_user.get_id)
        touch_saved_reports_views(request.couch_user, self.domain)

        return json_response(self.config)

    @property
    @memoized
    def config(self):
        config = ReportConfig.get_or_create(
            self.saved_report_config_form.cleaned_data['_id']
        )
        if config.owner_id:
            # in case a user maliciously tries to edit another user's config
            assert config.owner_id == self.user_id
        else:
            config.domain = self.domain
            config.owner_id = self.user_id
        return config

    @property
    @memoized
    def saved_report_config_form(self):
        return SavedReportConfigForm(
            self.domain,
            self.user_id,
            self.post_data
        )

    @property
    def filters(self):
        filters = copy.copy(self.post_data.get('filters', {}))
        for field in ['startdate', 'enddate']:
            if field in filters:
                del filters[field]
        return filters

    @property
    def post_data(self):
        return json.loads(self.request.body)

    @property
    def user_id(self):
        return self.request.couch_user._id


@login_and_domain_required
@datespan_default
def email_report(request, domain, report_slug, report_type=ProjectReportDispatcher.prefix, once=False):
    from .forms import EmailReportForm

    form = EmailReportForm(request.GET)
    if not form.is_valid():
        return HttpResponseBadRequest()

    recipient_emails = set(form.cleaned_data['recipient_emails'])
    if form.cleaned_data['send_to_owner']:
        recipient_emails.add(request.couch_user.get_email())

    request_data = request_as_dict(request)

    send_email_report.delay(recipient_emails, domain, report_slug, report_type,
                            request_data, once, form.cleaned_data)
    return HttpResponse()


@login_and_domain_required
@require_http_methods(['DELETE'])
def delete_config(request, domain, config_id):
    try:
        config = ReportConfig.get(config_id)
    except ResourceNotFound:
        raise Http404()

    config.delete()
    ProjectReportsTab.clear_dropdown_cache(domain, request.couch_user.get_id)

    touch_saved_reports_views(request.couch_user, domain)
    return HttpResponse()


def normalize_hour(hour):
    day_change = 0
    if hour < 0:
        day_change = -1
        hour += 24
    elif hour >= 24:
        day_change = 1
        hour -= 24

    assert 0 <= hour < 24
    return (hour, day_change)


def calculate_hour(hour, hour_difference, minute_difference):
    hour -= hour_difference
    if hour_difference > 0 and minute_difference != 0:
        hour -= 1
    return normalize_hour(hour)


def recalculate_hour(hour, hour_difference, minute_difference):
    hour += hour_difference
    if hour_difference > 0 and minute_difference != 0:
        hour += 1
    return normalize_hour(hour)


def get_timezone_difference(domain):
    return datetime.now(pytz.timezone(Domain.get_by_name(domain)['default_timezone'])).strftime('%z')


def calculate_day(interval, day, day_change):
    if interval == "weekly":
        return (day + day_change) % 7
    elif interval == "monthly":
        return (day - 1 + day_change) % 31 + 1
    return day


class ScheduledReportsView(BaseProjectReportSectionView):
    urlname = 'edit_scheduled_report'
    page_title = _("Scheduled Report")
    template_name = 'reports/edit_scheduled_report.html'

    @use_multiselect
    @use_select2_v4
    @use_jquery_ui
    def dispatch(self, request, *args, **kwargs):
        return super(ScheduledReportsView, self).dispatch(request, *args, **kwargs)

    @property
    def scheduled_report_id(self):
        return self.kwargs.get('scheduled_report_id')

    def can_edit_report(self, report_instance):
        owner = report_instance.owner
        owner_domain = report_instance.domain
        current_user = self.request.couch_user
        return current_user.user_id == owner.user_id or current_user.is_domain_admin(owner_domain)

    @property
    @memoized
    def report_notification(self):
        if self.scheduled_report_id:
            instance = ReportNotification.get(self.scheduled_report_id)
            time_difference = get_timezone_difference(self.domain)
            (instance.hour, day_change) = recalculate_hour(
                instance.hour,
                int(time_difference[:3]),
                int(time_difference[3:])
            )
            instance.minute = 0
            if day_change:
                instance.day = calculate_day(instance.interval, instance.day, day_change)

            if not self.can_edit_report(instance):
                raise Http403()
        else:
            instance = ReportNotification(
                owner_id=self.request.couch_user._id,
                domain=self.domain,
                config_ids=[],
                hour=8,
                minute=0,
                send_to_owner=True,
                recipient_emails=[],
                language=None,
            )
        return instance

    @property
    def is_new(self):
        return self.report_notification.new_document

    @property
    def page_name(self):
        if not self.configs:
            return self.page_title
        if self.is_new:
            return _("New Scheduled Report")
        return _("Edit Scheduled Report")

    @property
    def owner_id(self):
        if self.scheduled_report_id:
            return ReportNotification.get(self.scheduled_report_id).owner_id
        else:
            return None

    @property
    @memoized
    def configs(self):
        user = self.request.couch_user
        if (self.scheduled_report_id and user.is_domain_admin(self.domain) and
                user._id != self.owner_id):
            return self.report_notification.configs
        return [
            c for c in ReportConfig.by_domain_and_owner(self.domain, user._id)
            if c.report and c.report.emailable
        ]

    @property
    def config_choices(self):
        config_choices = [(c._id, c.full_name) for c in self.configs]

        def _sort_key(config_choice):
            config_choice_id = config_choice[0]
            if config_choice_id in self.report_notification.config_ids:
                return self.report_notification.config_ids.index(config_choice_id)
            else:
                return len(self.report_notification.config_ids)

        return sorted(config_choices, key=_sort_key)

    @property
    @memoized
    def scheduled_report_form(self):
        web_users = WebUser.view('users/web_users_by_domain', reduce=False,
                               key=self.domain, include_docs=True).all()
        initial = self.report_notification.to_json()
        kwargs = {'initial': initial}
        if self.request.method == "POST":
            args = (self.request.POST, )
            selected_emails = self.request.POST.getlist('recipient_emails', {})
        else:
            args = ()
            selected_emails = kwargs.get('initial', {}).get('recipient_emails', [])

        web_user_emails = [u.get_email() for u in web_users]
        for email in selected_emails:
            if email not in web_user_emails:
                web_user_emails = [email] + web_user_emails

        from corehq.apps.reports.forms import ScheduledReportForm
        form = ScheduledReportForm(*args, **kwargs)
        form.fields['config_ids'].choices = self.config_choices
        form.fields['recipient_emails'].choices = [(e, e) for e in web_user_emails]
        if not toggles.SET_SCHEDULED_REPORT_START_DATE.enabled(self.domain):
            form.fields.pop('start_date')

        form.fields['hour'].help_text = "This scheduled report's timezone is %s (%s GMT)" % \
                                        (Domain.get_by_name(self.domain)['default_timezone'],
                                        get_timezone_difference(self.domain)[:3] + ':'
                                        + get_timezone_difference(self.domain)[3:])
        return form

    @property
    def page_context(self):
        context = {
            'form': None,
            'report': {
                'show': user_can_view_reports(self.request.project, self.request.couch_user),
                'slug': None,
                'default_url': reverse('reports_home', args=(self.domain,)),
                'is_async': False,
                'section_name': ProjectReport.section_name,
                'title': self.page_name,
            }
        }

        if not self.configs and not self.request.couch_user.is_domain_admin(self.domain):
            return context

        is_configurable_map = {c._id: c.is_configurable_report for c in self.configs}
        languages_map = {c._id: list(c.languages | set(['en'])) for c in self.configs}
        languages_for_select = {tup[0]: tup for tup in langcodes.get_all_langs_for_select()}

        context.update({
            'form': self.scheduled_report_form,
            'day_value': getattr(self.report_notification, "day", 1),
            'weekly_day_options': ReportNotification.day_choices(),
            'monthly_day_options': [(i, i) for i in range(1, 32)],
            'form_action': _("Create a new") if self.is_new else _("Edit"),
            'is_configurable_map': is_configurable_map,
            'languages_map': languages_map,
            'languages_for_select': languages_for_select,
            'is_owner': self.is_new or self.request.couch_user._id == self.owner_id,
        })
        return context

    def post(self, request, *args, **kwargs):
        if self.scheduled_report_form.is_valid():
            for k, v in self.scheduled_report_form.cleaned_data.items():
                setattr(self.report_notification, k, v)

            time_difference = get_timezone_difference(self.domain)
            (self.report_notification.hour, day_change) = calculate_hour(
                self.report_notification.hour, int(time_difference[:3]), int(time_difference[3:])
            )
            self.report_notification.minute = int(time_difference[3:])
            if day_change:
                self.report_notification.day = calculate_day(
                    self.report_notification.interval,
                    self.report_notification.day,
                    day_change
                )

            self.report_notification.save()
            ProjectReportsTab.clear_dropdown_cache(self.domain, self.request.couch_user.get_id)
            if self.is_new:
                DomainAuditRecordEntry.update_calculations(self.domain, 'cp_n_saved_scheduled_reports')
                messages.success(request, _("Scheduled report added."))
            else:
                messages.success(request, _("Scheduled report updated."))

            touch_saved_reports_views(request.couch_user, self.domain)
            return HttpResponseRedirect(reverse('reports_home', args=(self.domain,)))

        return self.get(request, *args, **kwargs)


class ReportNotificationUnsubscribeView(TemplateView):
    template_name = 'reports/notification_unsubscribe.html'
    urlname = 'notification_unsubscribe'
    not_found_error = ugettext_noop('Could not find the requested Scheduled Report')
    broken_link_error = ugettext_noop('Invalid unsubscribe link')
    report = None

    def get(self, request, *args, **kwargs):
        if 'success' not in kwargs and 'error' not in kwargs:
            try:
                self.report = ReportNotification.get(kwargs.pop('scheduled_report_id'))
                email = kwargs.pop('user_email')

                if kwargs.pop('scheduled_report_secret') != self.report.get_secret(email):
                    raise ValidationError(self.broken_link_error)
                if email not in self.report.all_recipient_emails:
                    raise ValidationError(ugettext_noop('This email address has already been unsubscribed.'))
            except ResourceNotFound:
                kwargs['error'] = self.not_found_error
            except ValidationError as err:
                kwargs['error'] = err.message

        if 'error' in kwargs:
            messages.error(request, ugettext_lazy(kwargs['error']))
        elif 'success' in kwargs:
            messages.success(request, ugettext_lazy(kwargs['success']))

        return super(ReportNotificationUnsubscribeView, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(ReportNotificationUnsubscribeView, self).get_context_data(**kwargs)
        context.update({'report': self.report})
        return context

    def post(self, request, *args, **kwargs):
        try:
            self.report = ReportNotification.get(kwargs.pop('scheduled_report_id'))
            email = kwargs.pop('user_email')

            if kwargs.pop('scheduled_report_secret') != self.report.get_secret(email):
                raise ValidationError(self.broken_link_error)

            self.report.remove_recipient(email)

            if len(self.report.recipient_emails) > 0 or self.report.send_to_owner:
                self.report.save()
            else:
                self.report.delete()

            kwargs['success'] = ugettext_noop('Successfully unsubscribed from report notification.')
        except ResourceNotFound:
            kwargs['error'] = self.not_found_error
        except ValidationError as err:
            kwargs['error'] = err.message

        return self.get(request, *args, **kwargs)


@login_and_domain_required
@require_POST
def delete_scheduled_report(request, domain, scheduled_report_id):
    user = request.couch_user
    try:
        rep = ReportNotification.get(scheduled_report_id)
    except ResourceNotFound:
        # was probably already deleted by a fast-clicker.
        pass
    else:
        if user._id != rep.owner._id and not user.is_domain_admin(domain):
            return HttpResponseBadRequest()

        rep.delete()
        messages.success(request, "Scheduled report deleted!")
    return HttpResponseRedirect(reverse("reports_home", args=(domain,)))


@login_and_domain_required
def send_test_scheduled_report(request, domain, scheduled_report_id):

    try:
        send_delayed_report(scheduled_report_id)
    except Exception as e:
        import logging
        logging.exception(e)
        messages.error(request, _("An error occurred, message unable to send"))
    else:
        messages.success(request, _("Report sent to this report's recipients"))

    return HttpResponseRedirect(reverse("reports_home", args=(domain,)))


def get_scheduled_report_response(couch_user, domain, scheduled_report_id,
                                  email=True, attach_excel=False,
                                  send_only_active=False):
    """
    This function somewhat confusingly returns a tuple of: (response, excel_files)
    If attach_excel is false, excel_files will always be an empty list.
    If send_only_active is True, then only ReportConfigs that have a start_date
    in the past will be sent. If none of the ReportConfigs are valid, no email will
    be sent.
    """
    # todo: clean up this API?
    from django.http import HttpRequest

    request = HttpRequest()
    request.couch_user = couch_user
    request.user = couch_user.get_django_user()
    request.domain = domain
    request.couch_user.current_domain = domain

    notification = ReportNotification.get(scheduled_report_id)
    return _render_report_configs(
        request,
        notification.configs,
        notification.domain,
        notification.owner_id,
        couch_user,
        email,
        attach_excel=attach_excel,
        lang=notification.language,
        send_only_active=send_only_active,
    )


def _render_report_configs(request, configs, domain, owner_id, couch_user, email,
                           notes=None, attach_excel=False, once=False, lang=None,
                           send_only_active=False):
    """
    Renders only notification's main content, which then may be used to generate full notification body.
    """
    from dimagi.utils.web import get_url_base

    report_outputs = []
    excel_attachments = []
    format = Format.from_format(request.GET.get('format') or Format.XLS_2007)

    # Show only the report configs that have started their reporting period
    if send_only_active:
        configs = [c for c in configs if c.is_active]

    # Don't send an email if none of the reports configs have started
    if len(configs) == 0:
        return False, False

    for config in configs:
        content, excel_file = config.get_report_content(lang, attach_excel=attach_excel)
        if excel_file:
            excel_attachments.append({
                'title': config.full_name + "." + format.extension,
                'file_obj': excel_file,
                'mimetype': format.mimetype
            })
        date_range = config.get_date_range()
        report_outputs.append({
            'title': config.full_name,
            'url': config.url,
            'content': content,
            'is_active': config.is_active,
            'description': config.description,
            "startdate": date_range.get("startdate") if date_range else "",
            "enddate": date_range.get("enddate") if date_range else "",
        })

    return render(request, "reports/report_email_content.html", {
        "reports": report_outputs,
        "domain": domain,
        "couch_user": owner_id,
        "DNS_name": get_url_base(),
        "owner_name": couch_user.full_name or couch_user.get_email(),
        "email": email,
        "notes": notes,
        "report_type": _("once off report") if once else _("scheduled report"),
    }).content, excel_attachments


def render_full_report_notification(request, content, email=None, report_notification=None):
    """
    Renders full notification body with provided main content.
    """
    from dimagi.utils.web import get_url_base
    from django.http import HttpRequest

    if request is None:
        request = HttpRequest()

    unsub_link = None
    if report_notification and email:
        unsub_link = get_url_base() + reverse('notification_unsubscribe', kwargs={
            'scheduled_report_id': report_notification._id,
            'user_email': email,
            'scheduled_report_secret': report_notification.get_secret(email)
        })

    return render(request, "reports/report_email.html", {
        'email_content': content,
        'unsub_link': unsub_link
    })


@login_and_domain_required
def view_scheduled_report(request, domain, scheduled_report_id):
    content = get_scheduled_report_response(request.couch_user, domain, scheduled_report_id, email=False)[0]
    return render_full_report_notification(request, content)


@location_safe
class CaseDataView(BaseProjectReportSectionView):
    urlname = 'case_data'
    template_name = "reports/reportdata/case_data.html"
    page_title = ugettext_lazy("Case Data")
    http_method_names = ['get']

    @method_decorator(require_case_view_permission)
    @use_select2_v4
    @use_datatables
    def dispatch(self, request, *args, **kwargs):
        if not self.case_instance:
            messages.info(request,
                          _("Sorry, we couldn't find that case. If you think this "
                            "is a mistake please report an issue."))
            return HttpResponseRedirect(CaseListReport.get_url(domain=self.domain))
        if not (request.can_access_all_locations or
                user_can_access_case(self.domain, self.request.couch_user, self.case_instance)):
            raise location_restricted_exception(request)
        return super(CaseDataView, self).dispatch(request, *args, **kwargs)

    @property
    def case_id(self):
        return self.kwargs['case_id']

    @property
    @memoized
    def case_instance(self):
        try:
            case = CaseAccessors(self.domain).get_case(self.case_id)
            if case.domain != self.domain or case.is_deleted:
                return None
            return case
        except CaseNotFound:
            return None

    @property
    def page_name(self):
        return case_inline_display(self.case_instance)

    @property
    def page_url(self):
        return reverse(self.urlname, args=(self.domain, self.case_id,))

    @property
    def parent_pages(self):
        return [{
            'title': CaseListReport.name,
            'url': CaseListReport.get_url(domain=self.domain),
        }]

    @property
    def page_context(self):
        opening_transactions = self.case_instance.get_opening_transactions()
        if not opening_transactions:
            messages.error(self.request, _(
                "The case creation form could not be found. "
                "Usually this happens if the form that created the case is archived "
                "but there are other forms that updated the case. "
                "To fix this you can archive the other forms listed here."
            ))

        from corehq.apps.hqwebapp.templatetags.proptable_tags import get_tables_as_rows, get_default_definition
        wrapped_case = get_wrapped_case(self.case_instance)
        timezone = get_timezone_for_user(self.request.couch_user, self.domain)
        timezone = timezone.localize(datetime.utcnow()).tzinfo
        _get_tables_as_rows = partial(get_tables_as_rows, timezone=timezone)
        display = self.request.project.get_case_display(self.case_instance) or wrapped_case.get_display_config()
        show_transaction_export = toggles.COMMTRACK.enabled(self.request.user.username)

        def _get_case_url(case_id):
            return absolute_reverse(self.urlname, args=[self.domain, case_id])

        data = copy.deepcopy(wrapped_case.to_full_dict())
        default_properties = _get_tables_as_rows(data, display)
        dynamic_data = wrapped_case.dynamic_properties()

        for section in display:
            for row in section['layout']:
                for item in row:
                    dynamic_data.pop(item.get("expr"), None)

        if dynamic_data:
            dynamic_keys = sorted(dynamic_data.keys())
            definition = get_default_definition(
                dynamic_keys, num_columns=DYNAMIC_CASE_PROPERTIES_COLUMNS)

            dynamic_properties = _get_tables_as_rows(
                dynamic_data,
                definition,
            )
        else:
            dynamic_properties = None

        the_time_is_now = datetime.utcnow()
        tz_offset_ms = int(timezone.utcoffset(the_time_is_now).total_seconds()) * 1000
        tz_abbrev = timezone.localize(the_time_is_now).tzname()

        # ledgers
        def _product_name(product_id):
            try:
                return SQLProduct.objects.get(product_id=product_id).name
            except SQLProduct.DoesNotExist:
                return (_('Unknown Product ("{}")').format(product_id))

        ledger_map = LedgerAccessors(self.domain).get_case_ledger_state(self.case_id, ensure_form_id=True)
        for section, product_map in ledger_map.items():
            product_tuples = sorted(
                (_product_name(product_id), product_map[product_id]) for product_id in product_map
            )
            ledger_map[section] = product_tuples

        repeat_records = get_repeat_records_by_payload_id(self.domain, self.case_id)

        can_edit_data = self.request.couch_user.can_edit_data

        context = {
            "case_id": self.case_id,
            "case": self.case_instance,
            "show_case_rebuild": toggles.SUPPORT.enabled(self.request.user.username),
            "can_edit_data": can_edit_data,
            "is_usercase": self.case_instance.type == USERCASE_TYPE,

            "default_properties_as_table": default_properties,
            "dynamic_properties": dynamic_data,
            "dynamic_properties_as_table": dynamic_properties,
            "show_properties_edit": can_edit_data and has_privilege(self.request, privileges.DATA_CLEANUP),
            "case_actions": mark_safe(json.dumps(wrapped_case.actions())),
            "timezone": timezone,
            "tz_abbrev": tz_abbrev,
            "ledgers": ledger_map,
            "timezone_offset": tz_offset_ms,
            "show_transaction_export": show_transaction_export,
            "xform_api_url": reverse('single_case_forms', args=[self.domain, self.case_id]),
            "repeat_records": repeat_records,
        }
        context.update(case_hierarchy_context(self.case_instance, _get_case_url, timezone=timezone))
        return context


def form_to_json(domain, form, timezone):
    form_name = xmlns_to_name(
        domain,
        form.xmlns,
        app_id=form.app_id,
        lang=get_language(),
    )
    received_on = ServerTime(form.received_on).user_time(timezone).done().strftime("%Y-%m-%d %H:%M")

    return {
        'id': form.form_id,
        'received_on': received_on,
        'user': {
            "id": form.user_id or '',
            "username": form.metadata.username if form.metadata else '',
        },
        'readable_name': form_name,
    }


@location_safe
@require_case_view_permission
@login_and_domain_required
@require_GET
def case_forms(request, domain, case_id):
    case = get_case_or_404(domain, case_id)
    if not (request.can_access_all_locations or
                user_can_access_case(domain, request.couch_user, case)):
        raise location_restricted_exception(request)
    try:
        start_range = int(request.GET['start_range'])
        end_range = int(request.GET['end_range'])
    except (KeyError, ValueError):
        return HttpResponseBadRequest()

    slice = list(reversed(case.xform_ids))[start_range:end_range]
    forms = FormAccessors(domain).get_forms(slice, ordered=True)
    timezone = get_timezone_for_user(request.couch_user, domain)
    return json_response([
        form_to_json(domain, form, timezone) for form in forms
    ])


@location_safe
@require_case_view_permission
@login_and_domain_required
@require_GET
def case_property_changes(request, domain, case_id, case_property_name):
    """Returns all changes to a case property
    """

    case = get_case_or_404(domain, case_id)
    timezone = get_timezone_for_user(request.couch_user, domain)
    next_transaction = int(request.GET.get('next_transaction', 0))

    paged_changes, last_trasaction_checked = get_paged_changes_to_case_property(
        case,
        case_property_name,
        start=next_transaction,
    )

    changes = []
    for change in paged_changes:
        change_json = form_to_json(domain, change.transaction.form, timezone)
        change_json['new_value'] = change.new_value
        change_json['form_url'] = reverse('render_form_data', args=[domain, change.transaction.form.form_id])
        changes.append(change_json)

    return json_response({
        'changes': changes,
        'last_transaction_checked': last_trasaction_checked,
    })


@location_safe
@require_case_view_permission
@login_and_domain_required
@require_GET
def download_case_history(request, domain, case_id):
    case = get_case_or_404(domain, case_id)
    track_workflow(request.couch_user.username, "Case Data Page: Case History csv Downloaded")
    history = get_case_history(case)
    properties = set()
    for f in history:
        properties |= set(f.keys())
    properties = sorted(list(properties))
    columns = [properties]
    for f in history:
        columns.append([f.get(prop, '') for prop in properties])

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="case_history_{}.csv"'.format(case.name)

    writer = csv.writer(response)
    writer.writerows(zip(*columns))   # transpose the columns to rows
    return response


@location_safe
class CaseAttachmentsView(CaseDataView):
    urlname = 'single_case_attachments'
    template_name = "reports/reportdata/case_attachments.html"
    page_title = ugettext_lazy("Case Attachments")
    http_method_names = ['get']

    @method_decorator(login_and_domain_required)
    def dispatch(self, request, *args, **kwargs):
        if not can_view_attachments(request):
            return HttpResponseForbidden(_("You don't have permission to access this page."))
        return super(CaseAttachmentsView, self).dispatch(request, *args, **kwargs)

    @property
    def page_name(self):
        return "{} '{}'".format(
            _("Attachments for case"), super(CaseAttachmentsView, self).page_name
        )


@require_case_view_permission
@login_and_domain_required
@require_GET
def case_xml(request, domain, case_id):
    case = get_case_or_404(domain, case_id)
    version = request.GET.get('version', V2)
    return HttpResponse(case.to_xml(version), content_type='text/xml')


@require_case_view_permission
@require_permission(Permissions.edit_data)
@require_GET
def case_property_names(request, domain, case_id):
    case = get_case_or_404(domain, case_id)

    # We need to look at the export schema in order to remove any case properties that
    # have been deleted from the app. When the data dictionary is fully public, we can use that
    # so that users may deprecate those properties manually
    export_schema = CaseExportDataSchema.generate_schema_from_builds(domain, None, case.type)
    property_schema = export_schema.group_schemas[0]
    last_app_ids = get_latest_app_ids_and_versions(domain)
    all_property_names = {
        item.path[-1].name for item in property_schema.items
        if not is_occurrence_deleted(item.last_occurrences, last_app_ids) and '/' not in item.path[-1].name
    }
    try:
        # external_id is effectively a dynamic property: see CaseDisplayWrapper.dynamic_properties
        if case.external_id:
            all_property_names.add('external_id')
        all_property_names.remove('name')
    except KeyError:
        pass
    all_property_names = list(all_property_names)
    all_property_names.sort()

    return json_response(all_property_names)


@require_case_view_permission
@require_permission(Permissions.edit_data)
@require_POST
def edit_case_view(request, domain, case_id):
    if not (has_privilege(request, privileges.DATA_CLEANUP)):
        raise Http404()

    case = get_case_or_404(domain, case_id)
    user = request.couch_user

    old_properties = case.dynamic_case_properties()
    old_properties['external_id'] = None    # special handling below
    updates = _get_data_cleaning_updates(request, old_properties)

    case_block_kwargs = {}

    # User may also update external_id; see CaseDisplayWrapper.dynamic_properties
    if 'external_id' in updates:
        if updates['external_id'] != case.external_id:
            case_block_kwargs['external_id'] = updates['external_id']
        updates.pop('external_id')

    if updates:
        case_block_kwargs['update'] = updates

    if case_block_kwargs:
        submit_case_blocks([CaseBlock(case_id=case_id, **case_block_kwargs).as_string()],
            domain, username=user.username, user_id=user._id, device_id=__name__ + ".edit_case",
            xmlns=EDIT_FORM_XMLNS)
        messages.success(request, _('Case properties saved for %s.' % case.name))
    else:
        messages.success(request, _('No changes made to %s.' % case.name))
    return JsonResponse({'success': 1})


@require_case_view_permission
@require_permission(Permissions.edit_data)
@require_POST
def rebuild_case_view(request, domain, case_id):
    case = get_case_or_404(domain, case_id)
    rebuild_case_from_forms(domain, case_id, UserRequestedRebuild(user_id=request.couch_user.user_id))
    messages.success(request, _('Case %s was rebuilt from its forms.' % case.name))
    return HttpResponseRedirect(reverse('case_data', args=[domain, case_id]))


@require_case_view_permission
@require_permission(Permissions.edit_data)
@require_POST
def resave_case_view(request, domain, case_id):
    """Re-save the case to have it re-processed by pillows
    """
    case = get_case_or_404(domain, case_id)
    resave_case(domain, case)
    messages.success(
        request,
        _('Case %s was successfully saved. Hopefully it will show up in all reports momentarily.' % case.name),
    )
    return HttpResponseRedirect(reverse('case_data', args=[domain, case_id]))


@require_case_view_permission
@require_permission(Permissions.edit_data)
@require_POST
def close_case_view(request, domain, case_id):
    case = get_case_or_404(domain, case_id)
    if case.closed:
        messages.info(request, 'Case {} is already closed.'.format(case.name))
    else:
        device_id = __name__ + ".close_case_view"
        form_id = close_case(case_id, domain, request.couch_user, device_id)
        msg = _('''Case {name} has been closed.
            <a href="{url}" class="post-link">Undo</a>.
            You can also reopen the case in the future by archiving the last form in the case history.
        '''.format(
            name=case.name,
            url=reverse('undo_close_case', args=[domain, case_id, form_id]),
        ))
        messages.success(request, mark_safe(msg), extra_tags='html')
    return HttpResponseRedirect(reverse('case_data', args=[domain, case_id]))


@require_case_view_permission
@require_permission(Permissions.edit_data)
@require_POST
def undo_close_case_view(request, domain, case_id, xform_id):
    case = get_case_or_404(domain, case_id)
    if not case.closed:
        messages.info(request, 'Case {} is not closed.'.format(case.name))
    else:
        closing_form_id = xform_id
        assert closing_form_id in case.xform_ids
        form = FormAccessors(domain).get_form(closing_form_id)
        form.archive(user_id=request.couch_user._id)
        messages.success(request, 'Case {} has been reopened.'.format(case.name))
    return HttpResponseRedirect(reverse('case_data', args=[domain, case_id]))


@require_case_view_permission
@login_and_domain_required
@require_GET
def export_case_transactions(request, domain, case_id):
    case = get_case_or_404(domain, case_id)
    products_by_id = dict(SQLProduct.objects.filter(domain=domain).values_list('product_id', 'name'))

    headers = [
        _('case id'),
        _('case name'),
        _('section'),
        _('date'),
        _('product_id'),
        _('product_name'),
        _('transaction amount'),
        _('type'),
        _('ending balance'),
    ]

    def _make_row(transaction):
        return [
            transaction.case_id,
            case.name,
            transaction.section_id,
            transaction.report.date if transaction.report_id else '',
            transaction.product_id,
            products_by_id.get(transaction.product_id, _('unknown product')),
            transaction.quantity,
            transaction.type,
            transaction.stock_on_hand,
        ]

    query_set = StockTransaction.objects.select_related('report')\
        .filter(case_id=case_id).order_by('section_id', 'report__date')

    formatted_table = [
        [
            'stock transactions',
            [headers] + [_make_row(txn) for txn in query_set]
        ]
    ]
    tmp = io.StringIO()
    export_from_tables(formatted_table, tmp, 'xlsx')
    return export_response(tmp, 'xlsx', '{}-stock-transactions'.format(case.name))


def _get_form_context(request, domain, instance):
    timezone = get_timezone_for_user(request.couch_user, domain)
    try:
        assert domain == instance.domain
    except AssertionError:
        raise Http404()

    display = request.project.get_form_display(instance)
    context = {
        "domain": domain,
        "display": display,
        "timezone": timezone,
        "instance": instance,
        "user": request.couch_user,
        "request": request,
    }
    return context


def _get_form_render_context(request, domain, instance, case_id=None):
    context = _get_form_context(request, domain, instance)
    user = context['user']
    timezone = context['timezone']
    support_enabled = toggle_enabled(request, toggles.SUPPORT)

    form_data, question_list_not_found = get_readable_data_for_submission(instance)

    # Build ordered list of questions and dict of question values => responses
    # Question values will be formatted to be processed by XFormQuestionValueIterator,
    # for example "/data/group/repeat_group[2]/question_id"
    question_response_map, ordered_question_values = get_data_cleaning_data(form_data, instance)

    context.update({
        "context_case_id": case_id,
        "instance": instance,
        "is_archived": instance.is_archived,
        "form_source_download_url": get_form_source_download_url(instance),
        "edit_info": _get_edit_info(instance),
        "domain": domain,
        "question_list_not_found": question_list_not_found,
        "form_data": form_data,
        "question_response_map": question_response_map,
        "ordered_question_values": ordered_question_values,
        "tz_abbrev": timezone.localize(datetime.utcnow()).tzname(),
    })

    context.update(_get_cases_changed_context(domain, instance, case_id))
    context.update(_get_form_metadata_context(domain, instance, timezone, support_enabled))
    context.update(_get_display_options(request, domain, user, instance, support_enabled))
    context.update(_get_edit_info(instance))

    instance_history = []
    if instance.history:
        form_operations = {
            'archive': ugettext_lazy('Archive'),
            'unarchive': ugettext_lazy('Un-Archive'),
            'edit': ugettext_lazy('Edit'),
            'uuid_data_fix': ugettext_lazy('Duplicate ID fix')
        }
        for operation in instance.history:
            user_date = ServerTime(operation.date).user_time(timezone).done()
            instance_history.append({
                'readable_date': user_date.strftime("%Y-%m-%d %H:%M"),
                'readable_action': form_operations.get(operation.operation, operation.operation),
                'user_info': get_doc_info_by_id(domain, operation.user),
            })
    context['instance_history'] = instance_history

    return context


def _get_cases_changed_context(domain, form, case_id=None):
    case_blocks = extract_case_blocks(form)
    for i, block in enumerate(list(case_blocks)):
        if case_id and block.get(const.CASE_ATTR_ID) == case_id:
            case_blocks.pop(i)
            case_blocks.insert(0, block)
    cases = []
    from corehq.apps.hqwebapp.templatetags.proptable_tags import get_default_definition, get_tables_as_columns

    def _sorted_case_update_keys(keys):
        """Put common @ attributes at the bottom"""
        return sorted(keys, key=lambda k: (k[0] == '@', k))

    for b in case_blocks:
        this_case_id = b.get(const.CASE_ATTR_ID)
        try:
            this_case = CaseAccessors(domain).get_case(this_case_id) if this_case_id else None
            valid_case = True
        except ResourceNotFound:
            this_case = None
            valid_case = False

        if this_case and this_case.case_id:
            url = reverse('case_data', args=[domain, this_case.case_id])
        else:
            url = "#"

        definition = get_default_definition(
            _sorted_case_update_keys(list(b)),
            assume_phonetimes=(not form.metadata or
                               (form.metadata.deviceID != CLOUDCARE_DEVICE_ID)),
        )
        cases.append({
            "is_current_case": case_id and this_case_id == case_id,
            "name": case_inline_display(this_case),
            "table": get_tables_as_columns(b, definition, timezone=get_timezone_for_request()),
            "url": url,
            "valid_case": valid_case,
            "case_type": this_case.type if this_case and valid_case else None,
        })

    return {
        'cases': cases
    }


def _get_form_metadata_context(domain, form, timezone, support_enabled=False):
    meta = _top_level_tags(form).get('meta', None) or {}
    meta['received_on'] = json_format_datetime(form.received_on)
    meta['server_modified_on'] = json_format_datetime(form.server_modified_on) if form.server_modified_on else ''
    if support_enabled:
        meta['last_sync_token'] = form.last_sync_token

    from corehq.apps.hqwebapp.templatetags.proptable_tags import get_default_definition, get_tables_as_columns
    definition = get_default_definition(_sorted_form_metadata_keys(list(meta)))
    form_meta_data = get_tables_as_columns(meta, definition, timezone=timezone)
    if getattr(form, 'auth_context', None):
        auth_context = AuthContext(form.auth_context)
        auth_context_user_id = auth_context.user_id
        auth_user_info = get_doc_info_by_id(domain, auth_context_user_id)
    else:
        auth_user_info = get_doc_info_by_id(domain, None)
        auth_context = AuthContext(
            user_id=None,
            authenticated=False,
            domain=domain,
        )
    meta_userID = meta.get('userID')
    meta_username = meta.get('username')
    if meta_userID == 'demo_user':
        user_info = DocInfo(
            domain=domain,
            display='demo_user',
        )
    elif meta_username == 'admin':
        user_info = DocInfo(
            domain=domain,
            display='admin',
        )
    else:
        user_info = get_doc_info_by_id(domain, meta_userID)

    return {
        "form_meta_data": form_meta_data,
        "auth_context": auth_context,
        "auth_user_info": auth_user_info,
        "user_info": user_info,
    }


def _top_level_tags(form):
        """
        Returns a OrderedDict of the top level tags found in the xml, in the
        order they are found.

        """
        to_return = OrderedDict()

        element = form.get_xml_element()
        if element is None:
            return OrderedDict(sorted(form.form_data.items()))

        for child in element:
            # fix {namespace}tag format forced by ElementTree in certain cases (eg, <reg> instead of <n0:reg>)
            key = child.tag.split('}')[1] if child.tag.startswith("{") else child.tag
            if key == "Meta":
                key = "meta"
            to_return[key] = form.get_data('form/' + key)
        return to_return


def _sorted_form_metadata_keys(keys):
    def mycmp(x, y):
        foo = ('timeStart', 'timeEnd')
        bar = ('username', 'userID')

        if x in foo and y in foo:
            return -1 if foo.index(x) == 0 else 1
        elif x in foo or y in foo:
            return 0

        if x in bar and y in bar:
            return -1 if bar.index(x) == 0 else 1
        elif x in bar and y in bar:
            return 0

        return cmp(x, y)
    return sorted(keys, cmp=mycmp)


def _get_edit_info(instance):
    info = {
        'was_edited': False,
        'is_edit': False,
    }
    if instance.is_deprecated:
        info.update({
            'was_edited': True,
            'latest_version': instance.orig_id,
        })
    if getattr(instance, 'edited_on', None) and getattr(instance, 'deprecated_form_id', None):
        info.update({
            'is_edit': True,
            'edited_on': instance.edited_on,
            'previous_version': instance.deprecated_form_id
        })
    return info


def _get_display_options(request, domain, user, form, support_enabled):
    user_can_edit = (
        request and user and request.domain and user.can_edit_data()
    )
    show_edit_options = (
        user_can_edit
        and can_edit_form_location(domain, user, form)
    )
    show_edit_submission = (
        user_can_edit
        and has_privilege(request, privileges.DATA_CLEANUP)
        and not form.is_deprecated
    )

    show_resave = (
        user_can_edit and support_enabled
    )

    return {
        "show_edit_options": show_edit_options,
        "show_edit_submission": show_edit_submission,
        "show_resave": show_resave,
    }


def _get_location_safe_form(domain, user, instance_id):
    """Fetches a form and verifies that the user can access it."""
    form = get_form_or_404(domain, instance_id)
    if not can_edit_form_location(domain, user, form):
        raise PermissionDenied()
    return form


@location_safe
class FormDataView(BaseProjectReportSectionView):
    urlname = 'render_form_data'
    page_title = ugettext_lazy("Untitled Form")
    template_name = "reports/reportdata/form_data.html"
    http_method_names = ['get']

    @method_decorator(require_form_view_permission)
    @use_select2_v4
    def dispatch(self, request, *args, **kwargs):
        return super(FormDataView, self).dispatch(request, *args, **kwargs)

    @property
    def instance_id(self):
        return self.kwargs['instance_id']

    @property
    def page_url(self):
        return reverse(self.urlname, args=(self.domain, self.instance_id,))

    @property
    @memoized
    def xform_instance(self):
        return _get_location_safe_form(
            self.domain, self.request.couch_user, self.instance_id)

    @property
    @memoized
    def form_name(self):
        try:
            form_name = self.xform_instance.form_data["@name"]
        except KeyError:
            form_name = _("Untitled Form")
        return form_name

    @property
    def page_name(self):
        return self.form_name

    @property
    def parent_pages(self):
        return [{
            'title': inspect.SubmitHistory.name,
            'url': inspect.SubmitHistory.get_url(self.domain),
        }]

    @property
    def page_context(self):
        page_context = _get_form_render_context(self.request, self.domain, self.xform_instance)
        page_context.update({
            "slug": inspect.SubmitHistory.slug,
            "form_name": self.form_name,
            "form_received_on": self.xform_instance.received_on,
        })
        return page_context


@require_form_view_permission
@login_and_domain_required
@require_GET
def case_form_data(request, domain, case_id, xform_id):
    instance = get_form_or_404(domain, xform_id)
    context = _get_form_render_context(request, domain, instance, case_id)
    return JsonResponse({
        'html': render_to_string("reports/form/partials/single_form.html", context, request=request),
        'xform_id': xform_id,
        'question_response_map': context['question_response_map'],
        'ordered_question_values': context['ordered_question_values'],
    })


@require_form_view_permission
@login_and_domain_required
@require_GET
def download_form(request, domain, instance_id):
    instance = get_form_or_404(domain, instance_id)
    assert(domain == instance.domain)

    response = HttpResponse(content_type='application/xml')
    response.write(instance.get_xml())
    return response


@location_safe
class EditFormInstance(View):

    @method_decorator(require_form_view_permission)
    @method_decorator(require_permission(Permissions.edit_data))
    def dispatch(self, request, *args, **kwargs):
        return super(EditFormInstance, self).dispatch(request, args, kwargs)

    @staticmethod
    def _get_form_from_instance(instance):
        try:
            build = Application.get(instance.build_id)
        except ResourceNotFound:
            raise Http404(_('Application not found.'))

        forms = build.get_forms_by_xmlns(instance.xmlns)
        if not forms:
            raise Http404(_('Missing module or form information!'))
        non_shadow_forms = [form for form in forms if form.form_type != ShadowForm.form_type]
        return non_shadow_forms[0]

    @staticmethod
    def _form_instance_to_context_url(domain, instance):
        form = EditFormInstance._get_form_from_instance(instance)
        return reverse(
            'cloudcare_form_context',
            args=[domain, instance.build_id, form.get_module().id, form.id],
            params={'instance_id': instance.form_id}
        )

    def get(self, request, *args, **kwargs):
        domain = request.domain
        instance_id = self.kwargs.get('instance_id', None)

        def _error(msg):
            messages.error(request, mark_safe(msg))
            url = reverse('render_form_data', args=[domain, instance_id])
            return HttpResponseRedirect(url)

        if not (has_privilege(request, privileges.DATA_CLEANUP)) or not instance_id:
            raise Http404()

        instance = _get_location_safe_form(domain, request.couch_user, instance_id)
        context = _get_form_context(request, domain, instance)
        if not instance.app_id or not instance.build_id:
            deviceID = instance.metadata.deviceID
            if deviceID and deviceID == FORMPLAYER_DEVICE_ID:
                return _error(_(
                    "Could not detect the application or form for this submission. "
                    "A common cause is that the form was submitted via App or Form preview"
                ))
            else:
                return _error(_('Could not detect the application or form for this submission.'))

        user = CouchUser.get_by_user_id(instance.metadata.userID, domain)
        if not user:
            return _error(_('Could not find user for this submission.'))

        edit_session_data = get_user_contributions_to_touchforms_session(user)

        # add usercase to session
        form = self._get_form_from_instance(instance)

        try:
            validate_xform_for_edit(form.wrapped_xform())
        except EditFormValidationError as e:
            return _error(e)

        if form.uses_usercase():
            usercase_id = user.get_usercase_id()
            if not usercase_id:
                return _error(_('Could not find the user-case for this form'))
            edit_session_data[USERCASE_ID] = usercase_id

        case_blocks = extract_case_blocks(instance, include_path=True)
        if form.form_type == 'advanced_form' or form.form_type == "shadow_form":
            datums = EntriesHelper(form.get_app()).get_datums_meta_for_form_generic(form)
            for case_block in case_blocks:
                path = case_block.path[0]  # all case blocks in advanced forms are nested one level deep
                matching_datums = [datum for datum in datums if datum.action.form_element_name == path]
                if len(matching_datums) == 1:
                    edit_session_data[matching_datums[0].datum.id] = case_block.caseblock.get(const.CASE_ATTR_ID)
        else:
            # a bit hacky - the app manager puts the main case directly in the form, so it won't have
            # any other path associated with it. This allows us to differentiate from parent cases.
            # You might think that you need to populate other session variables like parent_id, but those
            # are never actually used in the form.
            non_parents = [cb for cb in case_blocks if cb.path == []]
            if len(non_parents) == 1:
                edit_session_data['case_id'] = non_parents[0].caseblock.get(const.CASE_ATTR_ID)
                case = CaseAccessors(domain).get_case(edit_session_data['case_id'])
                if case.closed:
                    return _error(_(
                        'Case <a href="{case_url}">{case_name}</a> is closed. Please reopen the '
                        'case before editing the form'
                    ).format(
                        case_url=reverse('case_data', args=[domain, case.case_id]),
                        case_name=case.name,
                    ))
                elif case.is_deleted:
                    return _error(
                        _('Case <a href="{case_url}">{case_name}</a> is deleted. Cannot edit this form.').format(
                            case_url=reverse('case_data', args=[domain, case.case_id]),
                            case_name=case.name,
                        )
                    )

        edit_session_data['is_editing'] = True
        edit_session_data['function_context'] = {
            'static-date': [
                {'name': 'now', 'value': instance.metadata.timeEnd},
                {'name': 'today', 'value': instance.metadata.timeEnd.date()},
            ]
        }

        context.update({
            'domain': domain,
            'maps_api_key': settings.GMAPS_API_KEY,  # used by cloudcare
            'form_name': _('Edit Submission'),  # used in breadcrumbs
            'use_sqlite_backend': use_sqlite_backend(domain),
            'username': context.get('user').username,
            'edit_context': {
                'formUrl': self._form_instance_to_context_url(domain, instance),
                'submitUrl': reverse('receiver_secure_post_with_app_id', args=[domain, instance.build_id]),
                'sessionData': edit_session_data,
                'returnUrl': reverse('render_form_data', args=[domain, instance_id]),
                'domain': domain,
            }
        })
        return render(request, 'reports/form/edit_submission.html', context)


@require_form_view_permission
@require_permission(Permissions.edit_data)
@require_POST
@location_safe
def restore_edit(request, domain, instance_id):
    if not (has_privilege(request, privileges.DATA_CLEANUP)):
        raise Http404()

    instance = _get_location_safe_form(domain, request.couch_user, instance_id)
    if instance.is_deprecated:
        submit_form_locally(instance.get_xml(), domain, app_id=instance.app_id, build_id=instance.build_id)
        messages.success(request, _('Form was restored from a previous version.'))
        return HttpResponseRedirect(reverse('render_form_data', args=[domain, instance.orig_id]))
    else:
        messages.warning(request, _('Sorry, that form cannot be edited.'))
        return HttpResponseRedirect(reverse('render_form_data', args=[domain, instance_id]))


@require_form_view_permission
@require_permission(Permissions.edit_data)
@require_POST
@location_safe
def archive_form(request, domain, instance_id):
    instance = _get_location_safe_form(domain, request.couch_user, instance_id)
    assert instance.domain == domain
    case_id_from_request, redirect = _get_case_id_and_redirect_url(domain, request)

    notify_level = messages.SUCCESS
    if instance.is_normal:
        cases_with_other_forms = _get_cases_with_other_forms(domain, instance)
        if cases_with_other_forms:
            notify_msg = _get_cases_with_forms_message(domain, cases_with_other_forms, case_id_from_request)
            notify_level = messages.ERROR
        else:
            instance.archive(user_id=request.couch_user._id)
            notify_msg = _("Form was successfully archived.")
    elif instance.is_archived:
        notify_msg = _("Form was already archived.")
    else:
        notify_msg = _("Can't archive documents of type %s. How did you get here??") % instance.doc_type
        notify_level = messages.ERROR

    params = {
        "notif": notify_msg,
        "undo": _("Undo"),
        "url": reverse('unarchive_form', args=[domain, instance_id]),
    }

    msg_template = "{notif} <a href='{url}' class='post-link'>{undo}</a>" if instance.is_archived else '{notif}'
    msg = msg_template.format(**params)
    messages.add_message(request, notify_level, mark_safe(msg), extra_tags='html')

    return HttpResponseRedirect(redirect)


def _get_cases_with_forms_message(domain, cases_with_other_forms, case_id_from_request):
    def _get_case_link(case_id, name):
        if case_id == case_id_from_request:
            return _("%(case_name)s (this case)") % {'case_name': name}
        else:
            return '<a href="{}#!history">{}</a>'.format(reverse('case_data', args=[domain, case_id]), name)

    case_links = ', '.join([
        _get_case_link(case_id, name)
        for case_id, name in cases_with_other_forms.items()
    ])
    msg = _("""Form cannot be archived as it creates cases that are updated by other forms.
        All other forms for these cases must be archived first:""")
    notify_msg = """{} {}""".format(msg, case_links)
    return notify_msg


def _get_cases_with_other_forms(domain, xform):
    """Get all cases touched by this form which also have other forms associated with them.
    :returns: Dict of Case ID -> Case"""
    cases_created = {u.id for u in get_case_updates(xform) if u.creates_case()}
    cases = {}
    for case in CaseAccessors(domain).iter_cases(list(cases_created)):
        if not case.is_deleted and case.xform_ids != [xform.form_id]:
            # case has other forms that need to be archived before this one
            cases[case.case_id] = case.name
    return cases


def _get_case_id_and_redirect_url(domain, request):
    case_id = None
    redirect = request.META.get('HTTP_REFERER')
    if not redirect:
        redirect = inspect.SubmitHistory.get_url(domain)
    else:
        # check if referring URL was a case detail view, then make sure
        # the case still exists before redirecting.
        template = reverse('case_data', args=[domain, 'fake_case_id'])
        template = template.replace('fake_case_id', '([^/]*)')
        case_id = re.findall(template, redirect)
        if case_id:
            case_id = case_id[0]
            try:
                case = CaseAccessors(domain).get_case(case_id)
                if case.is_deleted:
                    raise CaseNotFound
            except CaseNotFound:
                redirect = reverse('project_report_dispatcher', args=[domain, 'case_list'])
    return case_id, redirect


@require_form_view_permission
@require_permission(Permissions.edit_data)
@location_safe
def unarchive_form(request, domain, instance_id):
    instance = _get_location_safe_form(domain, request.couch_user, instance_id)
    assert instance.domain == domain
    if instance.is_archived:
        instance.unarchive(user_id=request.couch_user._id)
    else:
        assert instance.is_normal
    messages.success(request, _("Form was successfully restored."))

    redirect = request.META.get('HTTP_REFERER')
    if not redirect:
        redirect = reverse('render_form_data', args=[domain, instance_id])
    return HttpResponseRedirect(redirect)


def _get_data_cleaning_updates(request, old_properties):
    updates = {}
    properties = json.loads(request.POST.get('properties'))
    for prop, value in six.iteritems(properties):
        if prop not in old_properties or old_properties[prop] != value:
            updates[prop] = value
    return updates


@require_form_view_permission
@require_permission(Permissions.edit_data)
@require_POST
@location_safe
def edit_form(request, domain, instance_id):
    instance = _get_location_safe_form(domain, request.couch_user, instance_id)
    assert instance.domain == domain

    form_data, question_list_not_found = get_readable_data_for_submission(instance)
    old_properties, dummy = get_data_cleaning_data(form_data, instance)
    updates = _get_data_cleaning_updates(request, old_properties)

    if updates:
        errors = FormProcessorInterface(domain).update_responses(instance, updates, request.couch_user.get_id)
        if errors:
            messages.error(request, _('Could not update questions: {}').format(", ".join(errors)))
        else:
            messages.success(request, _('Question responses saved.'))
    else:
        messages.info(request, _('No changes made to form.'))

    return JsonResponse({'success': 1})


@require_form_view_permission
@require_permission(Permissions.edit_data)
@require_POST
@location_safe
def resave_form_view(request, domain, instance_id):
    """Re-save the form to have it re-processed by pillows
    """
    from corehq.form_processor.change_publishers import publish_form_saved
    instance = _get_location_safe_form(domain, request.couch_user, instance_id)
    assert instance.domain == domain
    resave_form(domain, instance)
    messages.success(request, _("Form was successfully resaved. It should reappear in reports shortly."))
    return HttpResponseRedirect(reverse('render_form_data', args=[domain, instance_id]))


# Weekly submissions by xmlns
def mk_date_range(start=None, end=None, ago=timedelta(days=7), iso=False):
    if isinstance(end, six.string_types):
        end = parse_date(end)
    if isinstance(start, six.string_types):
        start = parse_date(start)
    if not end:
        end = datetime.utcnow()
    if not start:
        start = end - ago
    if iso:
        return json_format_datetime(start), json_format_datetime(end)
    else:
        return start, end


def _is_location_safe_report_class(view_fn, request, domain, export_hash, format):
    cache = get_redis_client()

    content = cache.get(export_hash)
    if content is not None:
        report_class, report_file = content
        return report_class_is_location_safe(report_class)


@conditionally_location_safe(_is_location_safe_report_class)
@login_and_domain_required
@require_GET
def export_report(request, domain, export_hash, format):
    cache = get_redis_client()

    content = cache.get(export_hash)
    if content is not None:
        report_class, report_file = content
        if not request.couch_user.has_permission(domain, 'view_report', data=report_class):
            raise PermissionDenied()
        if format in Format.VALID_FORMATS:
            file = ContentFile(report_file)
            response = HttpResponse(file, Format.FORMAT_DICT[format])
            response['Content-Length'] = file.size
            response['Content-Disposition'] = 'attachment; filename="{filename}.{extension}"'.format(
                filename=export_hash,
                extension=Format.FORMAT_DICT[format]['extension']
            )
            return response
        else:
            return HttpResponseNotFound(_("We don't support this format"))
    else:
        return HttpResponseNotFound(_("That report was not found. Please remember"
                                      " that download links expire after 24 hours."))


@login_or_digest
@require_form_view_permission
@require_GET
def form_multimedia_export(request, domain):
    task_kwargs = {'domain': domain}
    try:
        task_kwargs['xmlns'] = request.GET["xmlns"]
        task_kwargs['startdate'] = request.GET["startdate"]
        task_kwargs['enddate'] = request.GET["enddate"]
        task_kwargs['enddate'] = json_format_date(string_to_datetime(task_kwargs['enddate']) + timedelta(days=1))
        task_kwargs['app_id'] = request.GET.get("app_id", None)
        task_kwargs['export_id'] = request.GET.get("export_id", None)
        task_kwargs['zip_name'] = request.GET.get("name", None)
    except (KeyError, ValueError):
        return HttpResponseBadRequest()

    download = DownloadBase()
    task_kwargs['download_id'] = download.download_id
    download.set_task(build_form_multimedia_zip.delay(**task_kwargs))

    return download.get_start_response()


@require_permission(Permissions.view_report, 'corehq.apps.reports.standard.project_health.ProjectHealthDashboard')
def project_health_user_details(request, domain, user_id):
    # todo: move to project_health.py? goes with project health dashboard.
    user = get_document_or_404(CommCareUser, domain, user_id)
    submission_by_form_link = '{}?emw=u__{}'.format(
        reverse('project_report_dispatcher', args=(domain, 'submissions_by_form')),
        user_id,
    )
    return render(request, 'reports/project_health/user_details.html', {
        'domain': domain,
        'user': user,
        'groups': ', '.join(g.name for g in Group.by_user(user)),
        'submission_by_form_link': submission_by_form_link,
    })
