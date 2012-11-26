from datetime import datetime, timedelta
import json
from django.core.cache import cache
from corehq.apps.reports import util
from corehq.apps.reports.standard import inspect, export, ProjectReport
from corehq.apps.reports.standard.export import DeidExportReport
from corehq.apps.reports.export import ApplicationBulkExportHelper, CustomBulkExportHelper
from corehq.apps.reports.models import (ReportConfig, ReportNotification,
    FormExportSchema, HQGroupExportConfiguration, UnsupportedScheduledReportError)
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.export import export_users
from corehq.apps.users.models import Permissions
import couchexport
from couchexport.export import UnsupportedExportFormat, export_raw
from couchexport.util import SerializableFunction
from couchforms.models import XFormInstance
from dimagi.utils.couch.loosechange import parse_date
from dimagi.utils.decorators import inline
from dimagi.utils.export import WorkBook
from dimagi.utils.web import json_request, json_response, render_to_response
from django.http import HttpResponseRedirect, HttpResponse, HttpResponseBadRequest, Http404, HttpResponseForbidden
from django.core.urlresolvers import reverse
from corehq.apps.domain.decorators import login_and_domain_required, login_or_digest
import couchforms.views as couchforms_views
from django.contrib import messages
from dimagi.utils.parsing import json_format_datetime, string_to_boolean
from django.contrib.auth.decorators import permission_required
from dimagi.utils.decorators.datespan import datespan_in_request
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.export import export_cases_and_referrals
from corehq.apps.reports.display import xmlns_to_name
from couchexport.schema import build_latest_schema
from couchexport.models import ExportSchema, ExportColumn, SavedExportSchema,\
    ExportTable, Format, FakeSavedExportSchema, SavedBasicExport
from couchexport import views as couchexport_views
from couchexport.shortcuts import export_data_shared, export_raw_data,\
    export_response
from django.views.decorators.http import (require_http_methods, require_POST,
    require_GET)
from couchforms.filters import instances
from couchdbkit.exceptions import ResourceNotFound
from fields import FilterUsersField
from util import get_all_users_by_domain
from corehq.apps.hqsofabed.models import HQFormData
from StringIO import StringIO
from corehq.apps.app_manager.util import get_app_id
from corehq.apps.groups.models import Group
from corehq.apps.adm import utils as adm_utils
from soil import DownloadBase
from soil.tasks import prepare_download
from django.utils.translation import ugettext as _
from django.utils.safestring import mark_safe

DATE_FORMAT = "%Y-%m-%d"

datespan_default = datespan_in_request(
    from_param="startdate",
    to_param="enddate",
    default_days=7,
)

require_form_export_permission = require_permission(Permissions.view_report, 'corehq.apps.reports.standard.export.ExcelExportReport', login_decorator=None)
require_case_export_permission = require_permission(Permissions.view_report, 'corehq.apps.reports.standard.export.CaseExportReport', login_decorator=None)

require_form_view_permission = require_permission(Permissions.view_report, 'corehq.apps.reports.standard.inspect.SubmitHistory', login_decorator=None)
require_case_view_permission = require_permission(Permissions.view_report, 'corehq.apps.reports.standard.inspect.CaseListReport', login_decorator=None)

require_can_view_all_reports = require_permission(Permissions.view_reports)

@login_and_domain_required
def default(request, domain, template="reports/reports_home.html"):
    user = request.couch_user
    if not request.couch_user.is_web_user():
        raise Http404

    configs = ReportConfig.by_domain_and_owner(domain, user._id).all()
    scheduled_reports = [s for s in ReportNotification.by_domain_and_owner(domain, user._id).all()
                         if not hasattr(s, 'report_slug') or s.report_slug != 'admin_domains']

    context = dict(
        couch_user=request.couch_user,
        domain=domain,
        configs=configs,
        scheduled_reports=scheduled_reports,
        report=dict(
            title="Select a Report to View",
            show=user.can_view_reports() or user.get_viewable_reports(),
            slug=None,
            is_async=True,
            app_slug="reports",
            section_name=ProjectReport.section_name,
            show_subsection_navigation=adm_utils.show_adm_nav(domain, request)
        ),
    )

    return render_to_response(request, template, context)

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

    group, users = util.get_group_params(domain, **json_request(req.GET))
    include_errors = string_to_boolean(req.GET.get("include_errors", False))

    kwargs = {"format": req.GET.get("format", Format.XLS_2007),
              "previous_export_id": req.GET.get("previous_export", None),
              "filename": export_tag,
              "use_cache": string_to_boolean(req.GET.get("use_cache", "True")),
              "max_column_size": int(req.GET.get("max_column_size", 2000)),
              "separator": req.GET.get("separator", "|")}

    user_filter, _ = FilterUsersField.get_user_filter(req)

    if user_filter:
        users_matching_filter = map(lambda x: x.get('user_id'), get_all_users_by_domain(domain,
            user_filter=user_filter, simplified=True))
        def _ufilter(user):
            try:
                return user['form']['meta']['userID'] in users_matching_filter
            except KeyError:
                return False
        filter = _ufilter
    else:
        filter = SerializableFunction(util.group_filter, group=group)

    errors_filter = instances if not include_errors else None

    kwargs['filter'] = couchexport.util.intersect_functions(filter, errors_filter)

    if kwargs['format'] == 'raw':
        resp = export_raw_data([domain, export_tag], filename=export_tag)
    else:
        try:
            resp = export_data_shared([domain,export_tag], **kwargs)
        except UnsupportedExportFormat as e:
            return HttpResponseBadRequest(e)
    if resp:
        return resp
    else:
        messages.error(req, "Sorry, there was no data found for the tag '%s'." % export_tag)
        next = req.GET.get("next", "")
        if not next:
            next = export.ExcelExportReport.get_url(domain=domain)
        return HttpResponseRedirect(next)

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

    filter = util.create_export_filter(request, domain, export_type=export_type)

    return couchexport_views.export_data_async(request, filter=filter, type=export_type)


class CustomExportHelper(object):

    class DEID(object):
        options = (
            ('', ''),
            ('Sensitive ID', 'couchexport.deid.deid_ID'),
            ('Sensitive Date', 'couchexport.deid.deid_date'),
        )

    def __init__(self, request, domain, export_id=None):
        self.request = request
        self.domain = domain
        self.export_type = request.GET.get('type', 'form')
        if self.export_type == 'form':
            self.ExportSchemaClass = FormExportSchema
        else:
            self.ExportSchemaClass = SavedExportSchema

        if export_id:
            self.custom_export = self.ExportSchemaClass.get(export_id)
            # also update the schema to include potential new stuff
            self.custom_export.update_schema()
            
            assert(self.custom_export.doc_type == 'SavedExportSchema')
            assert(self.custom_export.type == self.export_type)
            assert(self.custom_export.index[0] == domain)
        else:
            self.custom_export = self.ExportSchemaClass(type=self.export_type)
            if self.export_type == 'form':
                self.custom_export.app_id = request.GET.get('app_id')
        
    def update_custom_export(self):
        schema = ExportSchema.get(self.request.POST["schema"])
        self.custom_export.index = schema.index
        self.custom_export.schema_id = self.request.POST["schema"]
        self.custom_export.name = self.request.POST["name"]
        self.custom_export.default_format = self.request.POST["format"] or Format.XLS_2007
        self.custom_export.is_safe = bool(self.request.POST.get('is_safe'))

        table = self.request.POST["table"]
        cols = self.request.POST['order'].strip().split()

        @list
        @inline
        def export_cols():
            for col in cols:
                transform = self.request.POST.get('%s transform' % col) or None
                if transform:
                    transform = SerializableFunction.loads(transform)
                yield ExportColumn(
                    index=col,
                    display=self.request.POST["%s display" % col],
                    transform=transform
                )

        export_table = ExportTable(index=table, display=self.request.POST["name"], columns=export_cols)
        self.custom_export.tables = [export_table]
        self.custom_export.order = cols

        table_dict = dict([t.index, t] for t in self.custom_export.tables)
        if table in table_dict:
            table_dict[table].columns = export_cols
        else:
            self.custom_export.tables.append(ExportTable(index=table,
                display=self.custom_export.name,
                columns=export_cols))

        if self.export_type == 'form':
            self.custom_export.include_errors = bool(self.request.POST.get("include-errors"))
            self.custom_export.app_id = self.request.POST.get('app_id')

    def get_response(self):
        table_config = self.custom_export.table_configuration[0]
        slug = export.ExcelExportReport.slug if self.export_type == "form" else export.CaseExportReport.slug
        
        def show_deid_column():
            for col in table_config['column_configuration']:
                if col['transform']:
                    return True
            return False

        return render_to_response(self.request, "reports/reportdata/customize_export.html", {
            "saved_export": self.custom_export,
            "deid_options": CustomExportHelper.DEID.options,
            "DeidExportReport_name": DeidExportReport.name,
            "table_config": table_config,
            "slug": slug,
            "domain": self.domain,
            "show_deid_column": show_deid_column()
        })

@login_or_digest
@datespan_default
@require_GET
def export_default_or_custom_data(request, domain, export_id=None, bulk_export=False):
    """
    Export data from a saved export schema
    """

    deid = request.GET.get('deid') == 'true'
    if deid:
        return _export_deid(request, domain, export_id, bulk_export=bulk_export)
    else:
        return _export_no_deid(request, domain, export_id, bulk_export=bulk_export)

@require_permission('view_report', 'corehq.apps.reports.standard.export.DeidExportReport', login_decorator=None)
def _export_deid(request, domain, export_id=None, bulk_export=False):
    return _export_default_or_custom_data(request, domain, export_id, bulk_export=bulk_export, safe_only=True)

@require_form_export_permission
def _export_no_deid(request, domain, export_id=None, bulk_export=False):
    return _export_default_or_custom_data(request, domain, export_id, bulk_export=bulk_export)

def _export_default_or_custom_data(request, domain, export_id=None, bulk_export=False, safe_only=False):
    async = request.GET.get('async') == 'true'
    next = request.GET.get("next", "")
    format = request.GET.get("format", "")
    export_type = request.GET.get("type", "form")
    previous_export_id = request.GET.get("previous_export", None)
    filename = request.GET.get("filename", None)
    max_column_size = int(request.GET.get("max_column_size", 2000))

    filter = util.create_export_filter(request, domain, export_type=export_type)
    if bulk_export:
        try:
            is_custom = json.loads(request.GET.get("is_custom", "false"))
            export_tags = json.loads(request.GET.get("export_tags", "null") or "null")
        except ValueError:
            return HttpResponseBadRequest()


        export_helper = (CustomBulkExportHelper if is_custom else ApplicationBulkExportHelper)(
            domain=domain,
            safe_only=safe_only
        )

        return export_helper.prepare_export(export_tags, filter)

    elif export_id:
        # this is a custom export
        try:
            export_object = CustomExportHelper(request, domain, export_id).custom_export
            if safe_only and not export_object.is_safe:
                return HttpResponseForbidden()
        except ResourceNotFound:
            raise Http404()
    elif safe_only:
        return HttpResponseForbidden()
    else:
        if not async:
            # this function doesn't support synchronous export without a custom export object
            # if we ever want that (i.e. for HTML Preview) then we just need to give
            # FakeSavedExportSchema a download_data function (called below)
            return HttpResponseBadRequest()
        try:
            export_tag = json.loads(request.GET.get("export_tag", "null") or "null")
        except ValueError:
            return HttpResponseBadRequest()
        assert(export_tag[0] == domain)
        export_object = FakeSavedExportSchema(index=export_tag)

    if async:
        return export_object.export_data_async(
            filter=filter,
            filename=filename,
            previous_export_id=previous_export_id,
            format=format,
            max_column_size=max_column_size,
        )
    else:
        if not next:
            next = export.ExcelExportReport.get_url(domain=domain)
        resp = export_object.download_data(format, filter=filter)
        if resp:
            return resp
        else:
            messages.error(request, "Sorry, there was no data found for the tag '%s'." % export_object.name)
            return HttpResponseRedirect(next)

@require_form_export_permission
@login_and_domain_required
def custom_export(req, domain):
    """
    Customize an export
    """
    try:
        export_tag = [domain, json.loads(req.GET.get("export_tag", "null") or "null")]
    except ValueError:
        return HttpResponseBadRequest()

    helper = CustomExportHelper(req, domain)

    if req.method == "POST":
        helper.update_custom_export()
        helper.custom_export.save()
        messages.success(req, "Custom export created! You can continue editing here.")
        return HttpResponseRedirect("%s?type=%s" % (reverse("edit_custom_export",
                                            args=[domain, helper.custom_export.get_id]), helper.export_type))

    schema = build_latest_schema(export_tag)

    if schema:
        app_id = req.GET.get('app_id')
        helper.custom_export = helper.ExportSchemaClass.default(
            schema=schema,
            name="%s: %s" % (
                xmlns_to_name(domain, export_tag[1], app_id=app_id) if helper.export_type == "form" else export_tag[1],
                datetime.utcnow().strftime("%Y-%m-%d")
            ),
            type=helper.export_type
        )

        if helper.export_type == 'form':
            helper.custom_export.app_id = app_id
        return helper.get_response()
    else:
        messages.warning(req, "<strong>No data found for that form "
                      "(%s).</strong> Submit some data before creating an export!" % \
                      xmlns_to_name(domain, export_tag[1], app_id=None), extra_tags="html")
        return HttpResponseRedirect(export.ExcelExportReport.get_url(domain=domain))

@require_form_export_permission
@login_and_domain_required
def edit_custom_export(req, domain, export_id):
    """
    Customize an export
    """
    try:
        helper = CustomExportHelper(req, domain, export_id)
    except ResourceNotFound:
        raise Http404()
    if req.method == "POST":
        helper.update_custom_export()
        helper.custom_export.save()
    return helper.get_response()

@login_or_digest
@require_form_export_permission
@login_and_domain_required
@require_GET
def hq_download_saved_export(req, domain, export_id):
    export = SavedBasicExport.get(export_id)
    # quasi-security hack: the first key of the index is always assumed 
    # to be the domain
    assert domain == export.configuration.index[0]
    return couchexport_views.download_saved_export(req, export_id)
    
@login_or_digest
@require_form_export_permission
@login_and_domain_required
@require_GET
def export_all_form_metadata(req, domain):
    """
    Export metadata for _all_ forms in a domain.
    """
    format = req.GET.get("format", Format.XLS_2007)
    
    headers = ("domain", "instanceID", "received_on", "type", 
               "timeStart", "timeEnd", "deviceID", "username", 
               "userID", "xmlns", "version")
    def _form_data_to_row(formdata):
        def _key_to_val(formdata, key):
            if key == "type":  return xmlns_to_name(domain, formdata.xmlns, app_id=None)
            else:              return getattr(formdata, key)
        return [_key_to_val(formdata, key) for key in headers]
    
    temp = StringIO()
    data = (_form_data_to_row(f) for f in HQFormData.objects.filter(domain=domain))
    export_raw((("forms", headers),), (("forms", data),), temp)
    return export_response(temp, format, "%s_forms" % domain)
    
@require_form_export_permission
@login_and_domain_required
@require_POST
def delete_custom_export(req, domain, export_id):
    """
    Delete a custom export
    """
    try:
        saved_export = SavedExportSchema.get(export_id)
    except ResourceNotFound:
        return HttpResponseRedirect(req.META['HTTP_REFERER'])
    type = saved_export.type
    saved_export.delete()
    messages.success(req, "Custom export was deleted.")
    if type == "form":
        return HttpResponseRedirect(export.ExcelExportReport.get_url(domain=domain))
    else:
        return HttpResponseRedirect(export.CaseExportReport.get_url(domain=domain))

@login_and_domain_required
@require_POST
def add_config(request, domain=None):
    from datetime import datetime
    
    POST = json.loads(request.raw_post_data)
    if 'name' not in POST or not POST['name']:
        return HttpResponseBadRequest()

    to_date = lambda s: datetime.strptime(s, '%Y-%m-%d').date() if s else s
    POST['start_date'] = to_date(POST['start_date'])
    POST['end_date'] = to_date(POST['end_date'])
    date_range = POST.get('date_range')
    if date_range == 'last7':
        POST['days'] = 7
    elif date_range == 'last30':
        POST['days'] = 30
    elif POST.get('days'):
        POST['days'] = int(POST['days'])
  
    exclude_filters = ['startdate', 'enddate']
    for field in exclude_filters:
        POST['filters'].pop(field, None)
    
    config = ReportConfig.get_or_create(POST.get('_id', None))

    if config.owner_id:
        assert config.owner_id == request.couch_user._id
    else:
        config.domain = domain
        config.owner_id = request.couch_user._id

    for field in config.properties().keys():
        if field in POST:
            setattr(config, field, POST[field])
    
    config.save()

    return json_response(config)

@login_and_domain_required
@require_http_methods(['DELETE'])
def delete_config(request, domain, config_id):
    try:
        config = ReportConfig.get(config_id)
    except ResourceNotFound:
        raise Http404()

    config.delete()
    return HttpResponse()


@login_and_domain_required
def edit_scheduled_report(request, domain, scheduled_report_id=None, 
                          template="reports/edit_scheduled_report.html"):
    from corehq.apps.users.models import WebUser
    from corehq.apps.reports.forms import ScheduledReportForm

    context = {
        'form': None,
        'domain': domain,
        'report': {
            'show': request.couch_user.can_view_reports() or request.couch_user.get_viewable_reports(),
            'slug': None,
            'default_url': reverse('reports_home', args=(domain,)),
            'is_async': False,
            'section_name': ProjectReport.section_name,
            'show_subsection_navigation': adm_utils.show_adm_nav(domain, request)
        }
    }
    
    user_id = request.couch_user._id

    configs = ReportConfig.by_domain_and_owner(domain, user_id).all()
    config_choices = [(c._id, c.full_name) for c in configs if c.report.emailable]

    if not config_choices:
        return render_to_response(request, template, context)

    web_users = WebUser.view('users/web_users_by_domain', reduce=False,
                               key=domain, include_docs=True).all()
    web_user_emails = [u.get_email() for u in web_users]

    if scheduled_report_id:
        instance = ReportNotification.get(scheduled_report_id)
        if instance.owner_id != user_id or instance.domain != domain:
            raise HttpResponseBadRequest()
    else:
        instance = ReportNotification(owner_id=user_id, domain=domain,
                                      config_ids=[], day_of_week=-1, hours=8,
                                      send_to_owner=True, recipient_emails=[])

    is_new = instance.new_document
    initial = instance.to_json()
    initial['recipient_emails'] = ', '.join(initial['recipient_emails'])

    kwargs = {'initial': initial}
    args = (request.POST,) if request.method == "POST" else ()
    form = ScheduledReportForm(*args, **kwargs)
    
    form.fields['config_ids'].choices = config_choices
    form.fields['recipient_emails'].choices = web_user_emails

    if request.method == "POST" and form.is_valid():
        for k, v in form.cleaned_data.items():
            setattr(instance, k, v)
        instance.save()

        if is_new:
            messages.success(request, "Scheduled report added!")
        else:
            messages.success(request, "Scheduled report updated!")

        return HttpResponseRedirect(reverse('reports_home', args=(domain,)))

    context['form'] = form
    if is_new:
        context['form_action'] = "Create a new"
        context['report']['title'] = "New Scheduled Report"
    else:
        context['form_action'] = "Edit"
        context['report']['title'] = "Edit Scheduled Report"

    return render_to_response(request, template, context)

@login_and_domain_required
@require_POST
def delete_scheduled_report(request, domain, scheduled_report_id):
    user_id = request.couch_user._id
    rep = ReportNotification.get(scheduled_report_id)

    if user_id != rep.owner._id:
        return HttpResponseBadRequest()

    rep.delete()
    messages.success(request, "Scheduled report deleted!")
    return HttpResponseRedirect(reverse("reports_home", args=(domain,)))

@login_and_domain_required
def send_test_scheduled_report(request, domain, scheduled_report_id):
    from corehq.apps.reports.tasks import send_report
    from corehq.apps.users.models import CouchUser, CommCareUser, WebUser
    
    user_id = request.couch_user._id

    notification = ReportNotification.get(scheduled_report_id)
    try:
        user = WebUser.get_by_user_id(user_id, domain)
    except CouchUser.AccountTypeError:
        user = CommCareUser.get_by_user_id(user_id, domain)

    try:
        send_report.delay(notification._id)
    except Exception, e:
        import logging
        logging.exception(e)
        messages.error(request, "An error occured, message unable to send")
    else:
        messages.success(request, "Test message sent to %s" % user.get_email())

    return HttpResponseRedirect(reverse("reports_home", args=(domain,)))


def get_scheduled_report_response(couch_user, domain, scheduled_report_id):
    from dimagi.utils.web import get_url_base
    from django.http import HttpRequest
    
    request = HttpRequest()
    request.couch_user = couch_user
    request.user = couch_user.get_django_user()
    request.domain = domain
    request.couch_user.current_domain = domain

    notification = ReportNotification.get(scheduled_report_id)

    report_outputs = []
    try:
        for config in notification.configs:
            report_outputs.append({
                'title': config.full_name,
                'url': config.url,
                'content': config.get_report_content()
            })
    except UnsupportedScheduledReportError:
        pass
    
    return render_to_response(request, "reports/report_email.html", {
        "reports": report_outputs,
        "domain": notification.domain,
        "couch_user": notification.owner._id,
        "DNS_name": get_url_base(),
    })

@login_and_domain_required
@permission_required("is_superuser")
def view_scheduled_report(request, domain, scheduled_report_id):
    return get_scheduled_report_response(request.couch_user, domain,
            scheduled_report_id)

@require_case_view_permission
@login_and_domain_required
@require_GET
def case_details(request, domain, case_id):
    timezone = util.get_timezone(request.couch_user.user_id, domain)

    try:
        case = CommCareCase.get(case_id)
    except ResourceNotFound:
        case = None
    
    if case == None or case.doc_type != "CommCareCase" or case.domain != domain:
        messages.info(request, "Sorry, we couldn't find that case. If you think this is a mistake plase report an issue.")
        return HttpResponseRedirect(inspect.CaseListReport.get_url(domain=domain))

    report_name = 'Details for Case "%s"' % case.name
    form_lookups = dict((form.get_id,
                         "%s: %s" % (form.received_on.date(), 
                                     xmlns_to_name(domain, form.xmlns, get_app_id(form)))) \
                        for form in case.get_forms())
    return render_to_response(request, "reports/reportdata/case_details.html", {
        "domain": domain,
        "case_id": case_id,
        "form_lookups": form_lookups,
        "slug":inspect.CaseListReport.slug,
        "report": dict(
            name=report_name,
            slug=inspect.CaseListReport.slug,
            is_async=False,
        ),
        "layout_flush_content": True,
        "timezone": timezone
    })

def generate_case_export_payload(domain, include_closed, format, group, user_filter):
    view_name = 'hqcase/all_cases' if include_closed else 'hqcase/open_cases'
    key = [domain, {}, {}]
    cases = CommCareCase.view(view_name, startkey=key, endkey=key + [{}], reduce=False, include_docs=True)
    # todo deal with cached user dict here
    users = get_all_users_by_domain(domain, group=group, user_filter=user_filter)
    groups = Group.get_case_sharing_groups(domain)

    #    if not group:
    #        users.extend(CommCareUser.by_domain(domain, is_active=False))

    workbook = WorkBook()
    export_cases_and_referrals(cases, workbook, users=users, groups=groups)
    export_users(users, workbook)
    payload = workbook.format(format.slug)
    return payload

@login_or_digest
@require_case_export_permission
@login_and_domain_required
@require_GET
def download_cases(request, domain):
    include_closed = json.loads(request.GET.get('include_closed', 'false'))
    format = Format.from_format(request.GET.get('format') or Format.XLS_2007)
    view_name = 'hqcase/all_cases' if include_closed else 'hqcase/open_cases'
    group = request.GET.get('group', None)
    user_filter, _ = FilterUsersField.get_user_filter(request)

    async = request.GET.get('async') == 'true'

    kwargs = {
        'domain': domain,
        'include_closed': include_closed,
        'format': format,
        'group': group,
        'user_filter': user_filter,
    }
    payload_func = SerializableFunction(generate_case_export_payload, **kwargs)
    content_disposition = "attachment; filename={domain}_data.{ext}".format(domain=domain, ext=format.extension)
    mimetype = "%s" % format.mimetype

    def generate_payload(payload_func):
        if async:
            download = DownloadBase()
            a_task = prepare_download.delay(download.download_id, payload_func,
                                            content_disposition, mimetype)
            download.set_task(a_task)
            return download.get_start_response()
        else:
            payload = payload_func()
            response = HttpResponse(payload)
            response['Content-Type'] = mimetype
            response['Content-Disposition'] = content_disposition
            return response

    return generate_payload(payload_func)


@require_form_view_permission
@login_and_domain_required
@require_GET
def form_data(request, domain, instance_id):
    timezone = util.get_timezone(request.couch_user.user_id, domain)
    try:
        instance = XFormInstance.get(instance_id)
    except Exception:
        raise Http404()
    try:
        assert(domain == instance.domain)
    except AssertionError:
        raise Http404()
    cases = CommCareCase.view("case/by_xform_id", key=instance_id, reduce=False, include_docs=True).all()
    try:
        form_name = instance.get_form["@name"]
    except KeyError:
        form_name = "Untitled Form"
    is_archived = instance.doc_type == "XFormArchived"
    if is_archived:
        messages.info(request, _("This form is archived. To restore it, click 'Restore this form' at the bottom of the page."))
    return render_to_response(request, "reports/reportdata/form_data.html",
                              dict(domain=domain,
                                   instance=instance,
                                   cases=cases,
                                   timezone=timezone,
                                   slug=inspect.SubmitHistory.slug,
                                   is_archived=is_archived,
                                   form_data=dict(name=form_name,
                                                  modified=instance.received_on)))

@require_form_view_permission
@login_and_domain_required
@require_GET
def download_form(request, domain, instance_id):
    instance = XFormInstance.get(instance_id)
    assert(domain == instance.domain)
    return couchforms_views.download_form(request, instance_id)

@require_form_view_permission
@login_and_domain_required
@require_GET
def download_attachment(request, domain, instance_id, attachment):
    instance = XFormInstance.get(instance_id)
    assert(domain == instance.domain)
    return couchforms_views.download_attachment(request, instance_id, attachment)

@require_form_view_permission
@require_permission(Permissions.edit_data)
@require_POST
def archive_form(request, domain, instance_id):
    instance = XFormInstance.get(instance_id)
    assert instance.domain == domain
    if instance.doc_type == "XFormInstance": 
        instance.archive()
        notif_msg = _("Form was successfully archived.")
    elif instance.doc_type == "XFormArchived":
        notif_msg = _("Form was already archived.")
    else:
        notif_msg = _("Can't archive documents of type %(s). How did you get here??") % instance.doc_type
    
    params = {
        "notif": notif_msg,
        "undo": _("Undo"),
        "url": reverse('render_form_data', args=[domain, instance_id])
    }
    msg_template = '%(notif)s <a href="%(url)s">%(undo)s</a>' if instance.doc_type == "XFormArchived" else '%(notif)s'
    msg = msg_template % params
    messages.success(request, mark_safe(msg), extra_tags='html')
    return HttpResponseRedirect(inspect.SubmitHistory.get_url(domain))

@require_form_view_permission
@require_permission(Permissions.edit_data)
def unarchive_form(request, domain, instance_id):
    instance = XFormInstance.get(instance_id)
    assert instance.domain == domain
    if instance.doc_type == "XFormArchived":
        instance.doc_type = "XFormInstance"
        instance.save()
    else:
        assert instance.doc_type == "XFormInstance"
    messages.success(request, _("Form was successfully restored."))
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



@login_and_domain_required
@permission_required("is_superuser")
def clear_report_caches(request, domain):
    print "CLEARING CACHE FOR DOMAIN", domain
    print "ALL CACHES", cache.all()
    return HttpResponse("TESTING")
