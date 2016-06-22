from copy import copy
from datetime import datetime, timedelta, date
import itertools
import json

from django.views.generic.base import TemplateView

from corehq.apps.app_manager.suite_xml.sections.entries import EntriesHelper
from corehq.apps.domain.views import BaseDomainView
from corehq.apps.hqwebapp.view_permissions import user_can_view_reports
from corehq.apps.reports.display import xmlns_to_name
from corehq.apps.tour.tours import REPORT_BUILDER_NO_ACCESS, \
    REPORT_BUILDER_ACCESS
from corehq.apps.users.permissions import FORM_EXPORT_PERMISSION, CASE_EXPORT_PERMISSION, \
    DEID_EXPORT_PERMISSION
from corehq.tabs.tabclasses import ProjectReportsTab
import langcodes
import os
import pytz
import re
from StringIO import StringIO
import tempfile
import unicodedata
from urllib2 import URLError

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.base import ContentFile
from django.core.servers.basehttp import FileWrapper
from django.http import (
    Http404,
    HttpResponseBadRequest,
    HttpResponseForbidden,
    HttpResponseRedirect,
)
from django.http.response import (
    HttpResponse,
    HttpResponseNotFound,
    StreamingHttpResponse,
)
from django.shortcuts import render
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

from casexml.apps.case import const
from casexml.apps.case.cleanup import rebuild_case_from_forms, close_case
from casexml.apps.case.dbaccessors import get_open_case_ids_in_domain
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.templatetags.case_tags import case_inline_display
from casexml.apps.case.xform import extract_case_blocks
from casexml.apps.case.xml import V2
from casexml.apps.stock.models import StockTransaction
from couchdbkit.exceptions import ResourceNotFound
import couchexport
from corehq.form_processor.exceptions import XFormNotFound, CaseNotFound, AttachmentNotFound
from corehq.form_processor.interfaces.dbaccessors import FormAccessors, CaseAccessors
from corehq.form_processor.models import UserRequestedRebuild
from corehq.form_processor.utils import should_use_sql_backend
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
from couchforms.models import XFormDeprecated, XFormInstance
from dimagi.utils.chunked import chunked
from dimagi.utils.couch.bulk import wrapped_docs
from dimagi.utils.couch.cache.cache_core import get_redis_client
from dimagi.utils.couch.loosechange import parse_date
from dimagi.utils.decorators.datespan import datespan_in_request
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.logging import notify_exception
from dimagi.utils.parsing import (json_format_datetime, string_to_boolean,
                                  string_to_datetime, json_format_date)
from dimagi.utils.web import json_request, json_response
from django_prbac.utils import has_privilege
from soil import DownloadBase
from soil.tasks import prepare_download

from corehq import privileges, toggles
from corehq.apps.accounting.decorators import requires_privilege_json_response
from corehq.apps.app_manager.const import USERCASE_TYPE, USERCASE_ID
from corehq.apps.app_manager.models import Application
from corehq.apps.cloudcare.touchforms_api import get_user_contributions_to_touchforms_session
from corehq.apps.data_interfaces.dispatcher import DataInterfaceDispatcher
from corehq.apps.domain.decorators import (
    login_and_domain_required,
    login_or_digest,
    login_or_digest_or_basic_or_apikey,
)
from corehq.apps.domain.models import Domain
from corehq.apps.export.custom_export_helpers import make_custom_export_helper
from corehq.apps.export.exceptions import BadExportConfiguration
from corehq.apps.groups.models import Group
from corehq.apps.hqcase.dbaccessors import get_case_ids_in_domain
from corehq.apps.hqcase.export import export_cases
from corehq.apps.hqwebapp.utils import csrf_inline
from corehq.apps.locations.permissions import can_edit_form_location
from corehq.apps.products.models import SQLProduct
from corehq.apps.receiverwrapper import submit_form_locally
from corehq.apps.userreports.util import default_language as ucr_default_language
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.export import export_users
from corehq.apps.users.models import (
    CommCareUser,
    CouchUser,
    Permissions,
    WebUser,
)
from corehq.util.couch import get_document_or_404
from corehq.util.spreadsheets.export import WorkBook
from corehq.util.timezones.utils import get_timezone_for_user
from corehq.util.view_utils import absolute_reverse, reverse

from .dispatcher import ProjectReportDispatcher
from .export import (
    ApplicationBulkExportHelper,
    CustomBulkExportHelper,
    save_metadata_export_to_tempfile,
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
    create_metadata_export,
    rebuild_export_async,
    rebuild_export_task,
    send_delayed_report,
)
from .templatetags.xform_tags import render_form
from .util import (
    create_export_filter,
    get_all_users_by_domain,
    get_group,
    group_filter,
    users_matching_filter,
)
from corehq.apps.style.decorators import (
    use_jquery_ui,
    use_select2,
    use_datatables,
    use_multiselect,
)


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


@login_and_domain_required
def default(request, domain):
    module = Domain.get_module_by_name(domain)
    if hasattr(module, 'DEFAULT_REPORT_CLASS'):
        return HttpResponseRedirect(getattr(module, 'DEFAULT_REPORT_CLASS').get_url(domain))
    return HttpResponseRedirect(reverse(MySavedReportsView.urlname, args=[domain]))


@login_and_domain_required
def old_saved_reports(request, domain):
    return default(request, domain)


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


class MySavedReportsView(BaseProjectReportSectionView):
    urlname = 'saved_reports'
    page_title = _("My Saved Reports")
    template_name = 'reports/reports_home.html'

    @use_jquery_ui
    @use_datatables
    def dispatch(self, request, *args, **kwargs):
        self._init_tours()
        return super(MySavedReportsView, self).dispatch(request, *args, **kwargs)

    def _init_tours(self):
        """
        Add properties to the request for any tour that might be active
        """
        if self.request.user.is_authenticated():
            tours = ((REPORT_BUILDER_ACCESS, 1), (REPORT_BUILDER_NO_ACCESS, 2))
            for tour, step in tours:
                if tour.should_show(self.request, step, self.request.GET.get('tour', False)):
                    self.request.guided_tour = tour.get_tour_data(self.request, step)
                    break  # Only one of these tours may be active.

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
                hasattr(rn, "_id") and rn._id
                and (not hasattr(rn, 'report_slug')
                     or rn.report_slug != 'admin_domains')
            )

        scheduled_reports = [
            r for r in ReportNotification.by_domain_and_owner(
                self.domain, self.request.couch_user._id)
            if _is_valid(r)
        ]
        scheduled_reports = sorted(scheduled_reports,
                                   key=lambda s: s.configs[0].name)
        for report in scheduled_reports:
            time_difference = get_timezone_difference(self.domain)
            (report.hour, day_change) = recalculate_hour(
                report.hour,
                int(time_difference[:3]),
                int(time_difference[3:])
            )
            report.minute = 0
            if day_change:
                report.day = calculate_day(report.interval, report.day, day_change)
        return scheduled_reports

    @property
    def page_context(self):
        return {
            'couch_user': self.request.couch_user,
            'configs': self.good_configs,
            'scheduled_reports': self.scheduled_reports,
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
        except BadExportConfiguration, e:
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
        except SchemaMismatchException, e:
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
@login_or_digest_or_basic_or_apikey(default='digest')
@require_form_export_permission
@require_GET
def hq_download_saved_export(req, domain, export_id):
    saved_export = SavedBasicExport.get(export_id)
    return _download_saved_export(req, domain, saved_export)


@csrf_exempt
@login_or_digest_or_basic_or_apikey(default='digest')
@require_form_deid_export_permission
@require_GET
def hq_deid_download_saved_export(req, domain, export_id):
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
    return build_download_saved_export_response(
        payload, saved_export.configuration.format, saved_export.configuration.filename
    )


def build_download_saved_export_response(payload, format, filename):
    content_type = Format.from_format(format).mimetype
    response = StreamingHttpResponse(FileWrapper(payload), content_type=content_type)
    if format != 'html':
        # ht: http://stackoverflow.com/questions/1207457/convert-unicode-to-string-in-python-containing-extra-symbols
        normalized_filename = unicodedata.normalize(
            'NFKD', unicode(filename),
        ).encode('ascii', 'ignore')
        response['Content-Disposition'] = 'attachment; filename="%s"' % normalized_filename
    return response


def should_update_export(last_accessed):
    cutoff = datetime.utcnow() - timedelta(days=settings.SAVED_EXPORT_ACCESS_CUTOFF)
    return not last_accessed or last_accessed < cutoff


@login_or_digest
@require_form_export_permission
@require_POST
def hq_update_saved_export(req, domain):
    group_id = req.POST['group_export_id']
    index = int(req.POST['index'])
    group_config = get_document_or_404(HQGroupExportConfiguration, domain, group_id)
    config, schema = group_config.all_exports[index]
    rebuild_export_task.delay(group_id, index)
    messages.success(
        req,
        _('Data update for {} has started and the saved export will be automatically updated soon. '
          'Please refresh the page periodically to check the status.').format(config.name)
    )
    return HttpResponseRedirect(reverse(DataInterfaceDispatcher.name(),
                                        args=[domain, req.POST['report_slug']]))


@login_or_digest
@require_form_export_permission
@require_GET
def export_all_form_metadata(req, domain):
    """
    Export metadata for _all_ forms in a domain.
    """
    format = req.GET.get("format", Format.XLS_2007)
    tmp_path = save_metadata_export_to_tempfile(domain, format=format)

    return export_response(open(tmp_path), format, "%s_forms" % domain)


@login_or_digest
@require_form_export_permission
@require_GET
@datespan_in_request(from_param="startdate", to_param="enddate")
def export_all_form_metadata_async(req, domain):
    datespan = req.datespan if req.GET.get("startdate") and req.GET.get("enddate") else None
    group_id = req.GET.get("group")
    ufilter =  UserTypeFilter.get_user_filter(req)[0]
    users = get_all_users_by_domain(
        domain=domain,
        group=group_id,
        user_filter=ufilter,
        simplified=True,
        include_inactive=True
    )
    user_ids = filter(None, [u["user_id"] for u in users])
    format = req.GET.get("format", Format.XLS_2007)
    filename = "%s_forms" % domain

    download = DownloadBase()
    download.set_task(create_metadata_export.delay(
        download.download_id,
        domain,
        format=format,
        filename=filename,
        datespan=datespan,
        user_ids=user_ids,
    ))
    return download.get_start_response()


def touch_saved_reports_views(user, domain):
    """
    Hit the saved reports views so stale=update_after doesn't cause the user to
    see old or deleted data after a change when they next load the reports
    homepage.

    """
    ReportConfig.by_domain_and_owner(domain, user._id, limit=1, stale=False)
    ReportNotification.by_domain_and_owner(domain, user._id, limit=1, stale=False)


class AddSavedReportConfigView(View):
    name = 'add_report_config'

    @method_decorator(login_and_domain_required)
    def post(self, request, domain, *args, **kwargs):
        self.domain = domain

        if not self.saved_report_config_form.is_valid():
            errors = self.saved_report_config_form.errors.get('__all__', [])
            return HttpResponseBadRequest(', '.join(errors))

        update_config_data = copy(self.saved_report_config_form.cleaned_data)
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
        filters = copy(self.post_data.get('filters', {}))
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
    from corehq.apps.hqwebapp.tasks import send_html_email_async
    from forms import EmailReportForm
    user_id = request.couch_user._id

    form = EmailReportForm(request.GET)
    if not form.is_valid():
        return HttpResponseBadRequest()

    config = ReportConfig()
    # see ReportConfig.query_string()
    object.__setattr__(config, '_id', 'dummy')
    config.name = _("Emailed report")
    config.report_type = report_type

    config.report_slug = report_slug
    config.owner_id = user_id
    config.domain = domain

    config.start_date = request.datespan.startdate.date()
    if request.datespan.enddate:
        config.date_range = 'range'
        config.end_date = request.datespan.enddate.date()
    else:
        config.date_range = 'since'

    GET = dict(request.GET.iterlists())
    exclude = ['startdate', 'enddate', 'subject', 'send_to_owner', 'notes', 'recipient_emails']
    filters = {}
    for field in GET:
        if not field in exclude:
            filters[field] = GET.get(field)

    config.filters = filters

    subject = form.cleaned_data['subject'] or _("Email report from CommCare HQ")
    content = _render_report_configs(
        request, [config], domain, user_id, request.couch_user, True, lang=request.couch_user.language,
        notes=form.cleaned_data['notes'], once=once
    )[0]

    if form.cleaned_data['send_to_owner']:
        email = request.couch_user.get_email()
        body = render_full_report_notification(request, content).content

        send_html_email_async.delay(
            subject, email, body,
            email_from=settings.DEFAULT_FROM_EMAIL, ga_track=True,
            ga_tracking_info={'cd4': request.domain})

    if form.cleaned_data['recipient_emails']:
        for recipient in form.cleaned_data['recipient_emails']:
            body = render_full_report_notification(request, content).content
            send_html_email_async.delay(
                subject, recipient, body,
                email_from=settings.DEFAULT_FROM_EMAIL, ga_track=True,
                ga_tracking_info={'cd4': request.domain})

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
    @use_select2
    def dispatch(self, request, *args, **kwargs):
        return super(ScheduledReportsView, self).dispatch(request, *args, **kwargs)

    @property
    def scheduled_report_id(self):
        return self.kwargs.get('scheduled_report_id')

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

            if instance.owner_id != self.request.couch_user._id or instance.domain != self.domain:
                return HttpResponseBadRequest()
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
    @memoized
    def configs(self):
        return [
            c for c in ReportConfig.by_domain_and_owner(self.domain, self.request.couch_user._id)
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
        web_user_emails = [u.get_email() for u in web_users]
        initial = self.report_notification.to_json()
        initial['recipient_emails'] = ', '.join(initial['recipient_emails'])
        kwargs = {'initial': initial}
        args = ((self.request.POST, ) if self.request.method == "POST" else ())

        from corehq.apps.reports.forms import ScheduledReportForm
        form = ScheduledReportForm(*args, **kwargs)
        form.fields['config_ids'].choices = self.config_choices
        form.fields['recipient_emails'].choices = web_user_emails

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

        if not self.configs:
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
                messages.success(request, "Scheduled report added!")
            else:
                messages.success(request, "Scheduled report updated!")

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
    user_id = request.couch_user._id
    try:
        rep = ReportNotification.get(scheduled_report_id)
    except ResourceNotFound:
        # was probably already deleted by a fast-clicker.
        pass
    else:
        if user_id != rep.owner._id:
            return HttpResponseBadRequest()

        rep.delete()
        messages.success(request, "Scheduled report deleted!")
    return HttpResponseRedirect(reverse("reports_home", args=(domain,)))


@login_and_domain_required
def send_test_scheduled_report(request, domain, scheduled_report_id):

    user_id = request.couch_user._id

    notification = ReportNotification.get(scheduled_report_id)
    user = CouchUser.get_by_user_id(user_id, domain)

    try:
        send_delayed_report(notification)
    except Exception, e:
        import logging
        logging.exception(e)
        messages.error(request, "An error occured, message unable to send")
    else:
        messages.success(request, "Test message sent to %s" % user.get_email())

    return HttpResponseRedirect(reverse("reports_home", args=(domain,)))


def get_scheduled_report_response(couch_user, domain, scheduled_report_id, email=True, attach_excel=False):
    """
    This function somewhat confusingly returns a tuple of: (response, excel_files)
    If attach_excel is false, excel_files will always be an empty list.
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
    )


def _render_report_configs(request, configs, domain, owner_id, couch_user, email,
                           notes=None, attach_excel=False, once=False, lang=None):
    """
    Renders only notification's main content, which then may be used to generate full notification body.
    """
    from dimagi.utils.web import get_url_base

    report_outputs = []
    excel_attachments = []
    format = Format.from_format(request.GET.get('format') or Format.XLS_2007)

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
@permission_required("is_superuser")
def view_scheduled_report(request, domain, scheduled_report_id):
    content = get_scheduled_report_response(request.couch_user, domain, scheduled_report_id, email=False)[0]
    return render_full_report_notification(request, content)


class CaseDetailsView(BaseProjectReportSectionView):
    urlname = 'case_details'
    template_name = "reports/reportdata/case_details.html"
    page_title = ugettext_lazy("Case Details")
    http_method_names = ['get']

    @method_decorator(require_case_view_permission)
    @use_datatables
    def dispatch(self, request, *args, **kwargs):
        if not self.case_instance:
            messages.info(request,
                          "Sorry, we couldn't find that case. If you think this "
                          "is a mistake please report an issue.")
            return HttpResponseRedirect(CaseListReport.get_url(domain=self.domain))
        return super(CaseDetailsView, self).dispatch(request, *args, **kwargs)

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
    def page_context(self):
        opening_transactions = self.case_instance.get_opening_transactions()
        if not opening_transactions:
            messages.error(self.request, _(
                "The case creation form could not be found. "
                "Usually this happens if the form that created the case is archived "
                "but there are other forms that updated the case. "
                "To fix this you can archive the other forms listed here."
            ))
        return {
            "case_id": self.case_id,
            "case": self.case_instance,
            "case_display_options": {
                "display": self.request.project.get_case_display(self.case_instance),
                "timezone": get_timezone_for_user(self.request.couch_user, self.domain),
                "get_case_url": lambda case_id: absolute_reverse(
                    self.urlname, args=[self.domain, case_id]),
                "show_transaction_export": toggles.STOCK_TRANSACTION_EXPORT.enabled(
                    self.request.user.username),
            },
            "show_case_rebuild": toggles.SUPPORT.enabled(self.request.user.username),
            'is_usercase': self.case_instance.type == USERCASE_TYPE,
        }


@require_case_view_permission
@login_and_domain_required
@require_GET
def case_forms(request, domain, case_id):
    case = _get_case_or_404(domain, case_id)
    try:
        start_range = int(request.GET['start_range'])
        end_range = int(request.GET['end_range'])
    except (KeyError, ValueError):
        return HttpResponseBadRequest()

    def form_to_json(form):
        form_name = xmlns_to_name(
            domain,
            form.xmlns,
            app_id=form.app_id,
            lang=get_language(),
        )
        return {
            'id': form.form_id,
            'received_on': json_format_datetime(form.received_on),
            'user': {
                "id": form.user_id or '',
                "username": form.metadata.username if form.metadata else '',
            },
            'readable_name': form_name,
        }

    slice = list(reversed(case.xform_ids))[start_range:end_range]
    forms = FormAccessors(domain).get_forms(slice, ordered=True)
    return json_response([
        form_to_json(form) for form in forms
    ])


class CaseAttachmentsView(CaseDetailsView):
    urlname = 'single_case_attachments'
    template_name = "reports/reportdata/case_attachments.html"
    page_title = ugettext_lazy("Case Attachments")
    http_method_names = ['get']

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
    case = _get_case_or_404(domain, case_id)
    version = request.GET.get('version', V2)
    return HttpResponse(case.to_xml(version), content_type='text/xml')


@require_case_view_permission
@require_permission(Permissions.edit_data)
@require_POST
def rebuild_case_view(request, domain, case_id):
    case = _get_case_or_404(domain, case_id)
    rebuild_case_from_forms(domain, case_id, UserRequestedRebuild(user_id=request.couch_user.user_id))
    messages.success(request, _(u'Case %s was rebuilt from its forms.' % case.name))
    return HttpResponseRedirect(reverse('case_details', args=[domain, case_id]))


@require_case_view_permission
@require_permission(Permissions.edit_data)
@require_POST
def resave_case(request, domain, case_id):
    """Re-save the case to have it re-processed by pillows
    """
    from corehq.form_processor.change_publishers import publish_case_saved
    case = _get_case_or_404(domain, case_id)
    if should_use_sql_backend(domain):
        publish_case_saved(case)
    else:
        CommCareCase.get_db().save_doc(case._doc)  # don't just call save to avoid signals
    messages.success(
        request,
        _(u'Case %s was successfully saved. Hopefully it will show up in all reports momentarily.' % case.name),
    )
    return HttpResponseRedirect(reverse('case_details', args=[domain, case_id]))


@require_case_view_permission
@require_permission(Permissions.edit_data)
@require_POST
def close_case_view(request, domain, case_id):
    case = _get_case_or_404(domain, case_id)
    if case.closed:
        messages.info(request, u'Case {} is already closed.'.format(case.name))
    else:
        form_id = close_case(case_id, domain, request.couch_user)
        msg = _(u'''Case {name} has been closed.
            <a href="javascript:document.getElementById('{html_form_id}').submit();">Undo</a>.
            You can also reopen the case in the future by archiving the last form in the case history.
            <form id="{html_form_id}" action="{url}" method="POST">
                <input type="hidden" name="closing_form" value="{xform_id}" />
                {csrf_inline}
            </form>
        '''.format(
            name=case.name,
            html_form_id='undo-close-case',
            xform_id=form_id,
            csrf_inline=csrf_inline(request),
            url=reverse('undo_close_case', args=[domain, case_id]),
        ))
        messages.success(request, mark_safe(msg), extra_tags='html')
    return HttpResponseRedirect(reverse('case_details', args=[domain, case_id]))


@require_case_view_permission
@require_permission(Permissions.edit_data)
@require_POST
def undo_close_case_view(request, domain, case_id):
    case = _get_case_or_404(domain, case_id)
    if not case.closed:
        messages.info(request, u'Case {} is not closed.'.format(case.name))
    else:
        closing_form_id = request.POST['closing_form']
        assert closing_form_id in case.xform_ids
        form = FormAccessors(domain).get_form(closing_form_id)
        form.archive(user_id=request.couch_user._id)
        messages.success(request, u'Case {} has been reopened.'.format(case.name))
    return HttpResponseRedirect(reverse('case_details', args=[domain, case_id]))


@require_case_view_permission
@login_and_domain_required
@require_GET
def export_case_transactions(request, domain, case_id):
    case = _get_case_or_404(domain, case_id)
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
    tmp = StringIO()
    export_from_tables(formatted_table, tmp, 'xlsx')
    return export_response(tmp, 'xlsx', '{}-stock-transactions'.format(case.name))


def generate_case_export_payload(domain, include_closed, format, group, user_filter, process=None):
    """
    Returns a FileWrapper object, which only the file backend in django-soil supports

    """
    status = 'all' if include_closed else 'open'
    if include_closed:
        case_ids = get_case_ids_in_domain(domain)
    else:
        case_ids = get_open_case_ids_in_domain(domain)

    class stream_cases(object):

        def __init__(self, all_case_ids):
            self.all_case_ids = all_case_ids

        def __iter__(self):
            for case_ids in chunked(self.all_case_ids, 500):
                for case in wrapped_docs(CommCareCase, case_ids):
                    yield case

        def __len__(self):
            return len(self.all_case_ids)

    # todo deal with cached user dict here
    group = Group.get(group) if group else None
    users = get_all_users_by_domain(
        domain,
        group=group,
        user_filter=user_filter,
        include_inactive=True
    )
    groups = Group.get_case_sharing_groups(domain)

    fd, path = tempfile.mkstemp()
    with os.fdopen(fd, 'wb') as file:
        workbook = WorkBook(file, format)
        export_cases(
            domain,
            stream_cases(case_ids),
            workbook,
            filter_group=group,
            users=users,
            all_groups=groups,
            process=process
        )
        export_users(users, workbook)
        workbook.close()
    return FileWrapper(open(path))


@requires_privilege_json_response(privileges.API_ACCESS)
def download_cases(request, domain):
    return download_cases_internal(request, domain)


@login_or_digest
@require_case_export_permission
@require_GET
def download_cases_internal(request, domain):
    """
    bypass api access checks to allow internal use
    """
    include_closed = json.loads(request.GET.get('include_closed', 'false'))
    try:
        format = Format.from_format(request.GET.get('format') or Format.XLS_2007)
    except URLError as e:
        return HttpResponseBadRequest(e.reason)
    group = request.GET.get('group', None)
    user_filter, _ = UserTypeFilter.get_user_filter(request)

    async = request.GET.get('async') == 'true'

    kwargs = {
        'domain': domain,
        'include_closed': include_closed,
        'format': format,
        'group': group,
        'user_filter': user_filter,
    }
    payload_func = SerializableFunction(generate_case_export_payload, **kwargs)
    content_disposition = 'attachment; filename="{domain}_data.{ext}"'.format(domain=domain, ext=format.extension)
    content_type = "%s" % format.mimetype

    def generate_payload(payload_func):
        if async:
            download = DownloadBase()
            a_task = prepare_download.delay(download.download_id, payload_func,
                                            content_disposition, content_type)
            download.set_task(a_task)
            return download.get_start_response()
        else:
            payload = payload_func()
            response = HttpResponse(payload)
            response['Content-Type'] = content_type
            response['Content-Disposition'] = content_disposition
            return response

    return generate_payload(payload_func)


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
    context['form_render_options'] = context
    return context


def _get_form_or_404(domain, id):
    try:
        return FormAccessors(domain).get_form(id)
    except XFormNotFound:
        raise Http404()


def _get_case_or_404(domain, case_id):
    try:
        case = CaseAccessors(domain).get_case(case_id)
        if case.domain != domain or case.is_deleted:
            raise Http404()
        return case
    except CaseNotFound:
        raise Http404()


def _get_form_to_edit(domain, user, instance_id):
    form = _get_form_or_404(domain, instance_id)
    if not can_edit_form_location(domain, user, form):
        raise PermissionDenied()
    return form


class FormDataView(BaseProjectReportSectionView):
    urlname = 'render_form_data'
    page_title = ugettext_lazy("Untitled Form")
    template_name = "reports/reportdata/form_data.html"
    http_method_names = ['get']

    @method_decorator(require_form_view_permission)
    def dispatch(self, request, *args, **kwargs):
        if self.xform_instance is None:
            raise Http404()
        try:
            assert self.domain == self.xform_instance.domain
        except AssertionError:
            raise Http404()
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
        try:
            return FormAccessors(self.domain).get_form(self.instance_id)
        except XFormNotFound:
            return None

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
    def page_context(self):
        timezone = get_timezone_for_user(self.request.couch_user, self.domain)
        display = self.request.project.get_form_display(self.xform_instance)
        page_context = {
            "display": display,
            "timezone": timezone,
            "instance": self.xform_instance,
            "user": self.request.couch_user,
        }
        form_render_options = {
            'domain': self.domain,
            'request': self.request,
        }
        form_render_options.update(page_context)
        page_context.update({
            "slug": inspect.SubmitHistory.slug,
            "form_name": self.form_name,
            "form_received_on": self.xform_instance.received_on,
            'form_render_options': form_render_options,
        })
        return page_context


@require_form_view_permission
@login_and_domain_required
@require_GET
def case_form_data(request, domain, case_id, xform_id):
    instance = _get_form_or_404(domain, xform_id)
    context = _get_form_context(request, domain, instance)
    context['case_id'] = case_id
    context['side_pane'] = True
    return HttpResponse(render_form(instance, domain, options=context))


@require_form_view_permission
@login_and_domain_required
@require_GET
def download_form(request, domain, instance_id):
    instance = _get_form_or_404(domain, instance_id)
    assert(domain == instance.domain)

    response = HttpResponse(content_type='application/xml')
    response.write(instance.get_xml())
    return response


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

        form = build.get_form_by_xmlns(instance.xmlns)
        if not form:
            raise Http404(_('Missing module or form information!'))
        return form

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
            messages.error(request, msg)
            url = reverse('render_form_data', args=[domain, instance_id])
            return HttpResponseRedirect(url)

        if not (has_privilege(request, privileges.DATA_CLEANUP)) or not instance_id:
            raise Http404()

        instance = _get_form_to_edit(domain, request.couch_user, instance_id)
        context = _get_form_context(request, domain, instance)
        if not instance.app_id or not instance.build_id:
            return _error(_('Could not detect the application/form for this submission.'))

        user = get_document_or_404(CommCareUser, domain, instance.metadata.userID)
        edit_session_data = get_user_contributions_to_touchforms_session(user)

        # add usercase to session
        form = self._get_form_from_instance(instance)
        if form.uses_usercase():
            usercase_id = user.get_usercase_id()
            if not usercase_id:
                return _error(_('Could not find the user-case for this form'))
            edit_session_data[USERCASE_ID] = usercase_id

        case_blocks = extract_case_blocks(instance, include_path=True)
        if form.form_type == 'advanced_form':
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
            non_parents = filter(lambda cb: cb.path == [], case_blocks)
            if len(non_parents) == 1:
                edit_session_data['case_id'] = non_parents[0].caseblock.get(const.CASE_ATTR_ID)

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
            'edit_context': {
                'formUrl': self._form_instance_to_context_url(domain, instance),
                'submitUrl': reverse('receiver_secure_post_with_app_id', args=[domain, instance.build_id]),
                'sessionData': edit_session_data,
                'returnUrl': reverse('render_form_data', args=[domain, instance_id]),
            }
        })
        return render(request, 'reports/form/edit_submission.html', context)


@require_form_view_permission
@require_permission(Permissions.edit_data)
@require_POST
def restore_edit(request, domain, instance_id):
    if not (has_privilege(request, privileges.DATA_CLEANUP)):
        raise Http404()

    instance = _get_form_to_edit(domain, request.couch_user, instance_id)
    if isinstance(instance, XFormDeprecated):
        submit_form_locally(instance.get_xml(), domain, app_id=instance.app_id, build_id=instance.build_id)
        messages.success(request, _(u'Form was restored from a previous version.'))
        return HttpResponseRedirect(reverse('render_form_data', args=[domain, instance.orig_id]))
    else:
        messages.warning(request, _(u'Sorry, that form cannot be edited.'))
        return HttpResponseRedirect(reverse('render_form_data', args=[domain, instance_id]))


@login_or_digest
@require_form_view_permission
@require_GET
def download_attachment(request, domain, instance_id):
    attachment = request.GET.get('attachment', False)
    if not attachment:
        return HttpResponseBadRequest("Invalid attachment.")
    instance = _get_form_or_404(domain, instance_id)
    assert(domain == instance.domain)

    try:
        attach = FormAccessors(domain).get_attachment_content(instance_id, attachment)
    except AttachmentNotFound:
        raise Http404()

    return StreamingHttpResponse(streaming_content=FileWrapper(attach.content_stream),
                                 content_type=attach.content_type)


@require_form_view_permission
@require_permission(Permissions.edit_data)
@require_POST
def archive_form(request, domain, instance_id):
    instance = _get_form_to_edit(domain, request.couch_user, instance_id)
    assert instance.domain == domain
    if instance.is_normal:
        instance.archive(user_id=request.couch_user._id)
        notif_msg = _("Form was successfully archived.")
    elif instance.is_archived:
        notif_msg = _("Form was already archived.")
    else:
        notif_msg = _("Can't archive documents of type %s. How did you get here??") % instance.doc_type

    params = {
        "notif": notif_msg,
        "undo": _("Undo"),
        "url": reverse('unarchive_form', args=[domain, instance_id]),
        "id": "restore-%s" % instance_id,
        "csrf_inline": csrf_inline(request)
    }

    msg_template = u"""{notif} <a href="javascript:document.getElementById('{id}').submit();">{undo}</a>
        <form id="{id}" action="{url}" method="POST">{csrf_inline}</form>""" \
        if instance.is_archived else u'{notif}'
    msg = msg_template.format(**params)
    messages.success(request, mark_safe(msg), extra_tags='html')

    redirect = request.META.get('HTTP_REFERER')
    if not redirect:
        redirect = inspect.SubmitHistory.get_url(domain)

    # check if referring URL was a case detail view, then make sure
    # the case still exists before redirecting.
    template = reverse('case_details', args=[domain, 'fake_case_id'])
    template = template.replace('fake_case_id', '([^/]*)')
    case_id = re.findall(template, redirect)
    if case_id:
        try:
            case = CaseAccessors(domain).get_case(case_id[0])
            if case.is_deleted:
                raise CaseNotFound
        except CaseNotFound:
            redirect = reverse('project_report_dispatcher', args=[domain, 'case_list'])

    return HttpResponseRedirect(redirect)


@require_form_view_permission
@require_permission(Permissions.edit_data)
def unarchive_form(request, domain, instance_id):
    instance = _get_form_to_edit(domain, request.couch_user, instance_id)
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


@require_form_view_permission
@require_permission(Permissions.edit_data)
@require_POST
def resave_form(request, domain, instance_id):
    """Re-save the form to have it re-processed by pillows
    """
    from corehq.form_processor.change_publishers import publish_form_saved
    instance = _get_form_to_edit(domain, request.couch_user, instance_id)
    assert instance.domain == domain
    if should_use_sql_backend(domain):
        publish_form_saved(instance)
    else:
        XFormInstance.get_db().save_doc(instance.to_json())
    messages.success(request, _("Form was successfully resaved. It should reappear in reports shortly."))
    return HttpResponseRedirect(reverse('render_form_data', args=[domain, instance_id]))


# Weekly submissions by xmlns
def mk_date_range(start=None, end=None, ago=timedelta(days=7), iso=False):
    if isinstance(end, basestring):
        end = parse_date(end)
    if isinstance(start, basestring):
        start = parse_date(start)
    if not end:
        end = datetime.utcnow()
    if not start:
        start = end - ago
    if iso:
        return json_format_datetime(start), json_format_datetime(end)
    else:
        return start, end


@require_case_view_permission
@login_and_domain_required
@require_GET
def export_report(request, domain, export_hash, format):
    cache = get_redis_client()

    content = cache.get(export_hash)
    if content is not None:
        if format in Format.VALID_FORMATS:
            file = ContentFile(content)
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
