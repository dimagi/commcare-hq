from datetime import datetime, timedelta
import json
from corehq.apps.reports import util, standard
from corehq.apps.users.export import export_users
from corehq.apps.users.models import CouchUser, CommCareUser
import couchexport
from couchexport.util import FilterFunction
from couchforms.models import XFormInstance
from dimagi.utils.couch.loosechange import parse_date
from dimagi.utils.export import WorkBook
from dimagi.utils.web import json_request, render_to_response
from dimagi.utils.couch.database import get_db
from dimagi.utils.modules import to_function
from django.conf import settings
from django.http import HttpResponseRedirect, HttpResponse, HttpResponseBadRequest, HttpResponseForbidden, Http404, HttpResponseNotFound
from django.core.urlresolvers import reverse
from django_digest.decorators import httpdigest
from corehq.apps.domain.decorators import login_and_domain_required
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
    ExportTable, Format
from couchexport import views as couchexport_views
from couchexport.shortcuts import export_data_shared, export_raw_data
from django.views.decorators.http import require_POST
from couchforms.filters import instances
from couchdbkit.exceptions import ResourceNotFound
from fields import FilterUsersField
from util import get_all_users_by_domain

DATE_FORMAT = "%Y-%m-%d"

datespan_default = datespan_in_request(
    from_param="startdate",
    to_param="enddate",
    default_days=7,
)

def login_or_digest(fn):
    def safe_fn(request, domain, *args, **kwargs):
        if not request.user.is_authenticated():
            def _inner(request, domain, *args, **kwargs):
                couch_user = CouchUser.from_django_user(request.user)
                if couch_user.is_web_user() and couch_user.is_member_of(domain):
                    return fn(request, domain, *args, **kwargs)
                else:
                    return HttpResponseForbidden()
            return httpdigest(_inner)(request, domain, *args, **kwargs)
        else:
            return login_and_domain_required(fn)(request, domain, *args, **kwargs)
    return safe_fn



@login_and_domain_required
def default(request, domain):
    return HttpResponseRedirect(reverse("report_dispatcher", args=[domain, standard.SubmissionsByFormReport.slug]))

@login_or_digest
@datespan_default
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
        users_matching_filter = map(lambda x: x._id, get_all_users_by_domain(domain, filter_users=user_filter))
        def _ufilter(user):
            try:
                return user['form']['meta']['userID'] in users_matching_filter
            except KeyError:
                return False
        filter = _ufilter
    else:
        filter = util.create_group_filter(group)

    errors_filter = instances if not include_errors else None

    kwargs['filter'] = couchexport.util.intersect_filters(filter, errors_filter)

    if kwargs['format'] == 'raw':
        resp = export_raw_data([domain, export_tag], filename=export_tag)
    else:
        resp = export_data_shared([domain,export_tag], **kwargs)
    if resp:
        return resp
    else:
        messages.error(req, "Sorry, there was no data found for the tag '%s'." % export_tag)
        next = req.GET.get("next", "")
        if not next:
            next = reverse('report_dispatcher', args=[domain, standard.ExcelExportReport.slug])
        return HttpResponseRedirect(next)

@login_and_domain_required
@datespan_default
def export_data_async(req, domain):
    """
    Download all data for a couchdbkit model
    """

    try:
        export_tag = json.loads(req.GET.get("export_tag", "null") or "null")
    except ValueError:
        return HttpResponseBadRequest()

    app_id = req.GET.get('app_id', None)
    assert(export_tag[0] == domain)

    filter = FilterFunction(instances) & FilterFunction(util.app_export_filter, app_id=app_id)

    return couchexport_views.export_data_async(req, filter=filter)
    
@login_and_domain_required
def custom_export(req, domain):
    """
    Customize an export
    """
    try:
        export_tag = [domain, 
                      json.loads(req.GET.get("export_tag", "null") or "null")]
    except ValueError:
        return HttpResponseBadRequest()
    
    if req.method == "POST":
        
        table = req.POST["table"]
        cols = req.POST['order'].strip().split()
        export_cols = [ExportColumn(index=col,
                                    display=req.POST["%s_display" % col]) \
                       for col in cols]
        export_table = ExportTable(index=table, display=req.POST["name"],
                                   columns=export_cols)
        include_errors = req.POST.get("include-errors", "")
        filter_function = "couchforms.filters.instances" if not include_errors else ""

        export_def = SavedExportSchema(index=export_tag, 
                                       schema_id=req.POST["schema"],
                                       name=req.POST["name"],
                                       default_format=req.POST["format"] or Format.XLS_2007,
                                       tables=[export_table],
                                       filter_function=filter_function)
        export_def.save()
        messages.success(req, "Custom export created! You can continue editing here.")
        return HttpResponseRedirect(reverse("edit_custom_export", 
                                            args=[domain,export_def.get_id]))
        
    schema = build_latest_schema(export_tag)
    
    if schema:
        saved_export = SavedExportSchema.default(schema, name="%s: %s" %\
                                                 (xmlns_to_name(domain, export_tag[1]),
                                                  datetime.utcnow().strftime("%d-%m-%Y")))
        return render_to_response(req, "reports/reportdata/customize_export.html",
                                  {"saved_export": saved_export,
                                   "table_config": saved_export.table_configuration[0],
                                   "domain": domain})
    else:
        messages.warning(req, "<strong>No data found for that form "
                      "(%s).</strong> Submit some data before creating an export!" % \
                      xmlns_to_name(domain, export_tag[1]), extra_tags="html")
        return HttpResponseRedirect(reverse('report_dispatcher', args=[domain, standard.ExcelExportReport.slug]))
        
@login_and_domain_required
def edit_custom_export(req, domain, export_id):
    """
    Customize an export
    """
    saved_export = SavedExportSchema.get(export_id)
    table_dict = dict([t.index, t] for t in saved_export.tables)
    if req.method == "POST":
        table = req.POST["table"]
        
        cols = req.POST['order'].strip().split()#[col[:-4] for col in req.POST if col.endswith("_val")]
        export_cols = [ExportColumn(index=col, 
                                    display=req.POST["%s_display" % col]) \
                       for col in cols]
        schema = ExportSchema.get(req.POST["schema"])
        saved_export.index = schema.index 
        saved_export.schema_id = req.POST["schema"]
        saved_export.name = req.POST["name"]
        saved_export.order = cols
        saved_export.default_format = req.POST["format"] or Format.XLS_2007
        saved_export.filter_function = "couchforms.filters.instances" \
                if not req.POST.get("include-errors", "") else "" 
        
        if table in table_dict:
            table_dict[table].columns = export_cols
        else:
            saved_export.tables.append(ExportTable(index=table,
                                                   display=saved_export.name,
                                                   coluns=export_cols))
        saved_export.save()
    
    # not yet used, but will be when we support child table export
#    table_index = req.GET.get("table_id", None)
#    if table_index:
#        table_config = saved_export.get_table_configuration(table_index)
#    else:
    table_config = saved_export.table_configuration[0]
        
    return render_to_response(req, "reports/reportdata/customize_export.html",
                              {"saved_export": saved_export,
                               "table_config": table_config,
                               "domain": domain})

@login_and_domain_required
@require_POST
def delete_custom_export(req, domain, export_id):
    """
    Delete a custom export
    """
    saved_export = SavedExportSchema.get(export_id)
    saved_export.delete()
    messages.success(req, "Custom export was deleted.")
    return HttpResponseRedirect(reverse('report_dispatcher', args=[domain, standard.ExcelExportReport.slug]))

@login_or_digest
def export_custom_data(req, domain, export_id):
    """
    Export data from a saved export schema
    """
    saved_export = SavedExportSchema.get(export_id)
    group, users = util.get_group_params(domain, **json_request(req.GET))
    format = req.GET.get("format", "")
    next = req.GET.get("next", "")
    if not next:
        next = reverse('report_dispatcher', args=[domain, standard.ExcelExportReport.slug])

    user_filter, _ = FilterUsersField.get_user_filter(req)

    if user_filter:
        users_matching_filter = map(lambda x: x._id, get_all_users_by_domain(domain, filter_users=user_filter))
        def _ufilter(user):
            try:
                return user['form']['meta']['userID'] in users_matching_filter
            except KeyError:
                return False
        filter = _ufilter
    else:
        filter = util.create_group_filter(group)

    resp = saved_export.download_data(format, filter=filter)
    if resp:
        return resp
    else:
        messages.error(req, "Sorry, there was no data found for the tag '%s'." % saved_export.name)
        return HttpResponseRedirect(next)

@login_and_domain_required
def case_details(request, domain, case_id):
    report_name = "Case Details"
    try:
        case = CommCareCase.get(case_id)
        report_name = 'Details for Case "%s"' % case.name
    except ResourceNotFound:
        messages.info(request, "Sorry, we couldn't find that case. If you think this is a mistake plase report an issue.")
        return HttpResponseRedirect(reverse("submit_history_report", args=[domain]))


    form_lookups = dict((form.get_id,
                         "%s: %s" % (form.received_on.date(), xmlns_to_name(domain, form.xmlns))) \
                        for form in [XFormInstance.get(id) for id in case.xform_ids] \
                        if form)
    return render_to_response(request, "reports/reportdata/case_details.html", {
        "domain": domain,
        "case_id": case_id,
        "form_lookups": form_lookups,
        "report": {
            "name": report_name
        },
        "is_tabular": True
    })

@login_or_digest
@login_and_domain_required
def download_cases(request, domain):
    include_closed = json.loads(request.GET.get('include_closed', 'false'))
    format = Format.from_format(request.GET.get('format') or Format.XLS_2007)

    view_name = 'hqcase/all_cases' if include_closed else 'hqcase/open_cases'

    key = [domain, {}, {}]
    cases = CommCareCase.view(view_name, startkey=key, endkey=key + [{}], reduce=False, include_docs=True)
#    group, users = util.get_group_params(domain, **json_request(request.GET))
    group = request.GET.get('group', None)
    user_filter, _ = FilterUsersField.get_user_filter(request)
    users = get_all_users_by_domain(domain, group=group, filter_users=user_filter)
#    if not group:
#        users.extend(CommCareUser.by_domain(domain, is_active=False))

    workbook = WorkBook()
    export_cases_and_referrals(cases, workbook, users=users)
    export_users(users, workbook)
    response = HttpResponse(workbook.format(format.slug))
    response['Content-Type'] = "%s" % format.mimetype
    response['Content-Disposition'] = "attachment; filename={domain}_data.{ext}".format(domain=domain, ext=format.extension)
    return response

@login_and_domain_required
def form_data(request, domain, instance_id):
    instance = XFormInstance.get(instance_id)
    assert(domain == instance.domain)
    cases = CommCareCase.view("case/by_xform_id", key=instance_id, reduce=False, include_docs=True).all()
    return render_to_response(request, "reports/reportdata/form_data.html",
                              dict(domain=domain,
                                    instance=instance,
                                    cases=cases,
                                    form_data=dict(name=instance.get_form["@name"],
                                                    modified=instance.get_form["case"]["date_modified"])))

@login_and_domain_required
def download_form(request, domain, instance_id):
    instance = XFormInstance.get(instance_id)
    assert(domain == instance.domain)
    return couchforms_views.download_form(request, instance_id)

@login_and_domain_required
def download_attachment(request, domain, instance_id, attachment):
    instance = XFormInstance.get(instance_id)
    assert(domain == instance.domain)
    return couchforms_views.download_attachment(request, instance_id, attachment)

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
def emaillist(request, domain):
    """
    Test an email report 
    """
    # circular import
    from corehq.apps.reports.schedule.config import ScheduledReportFactory
    return render_to_response(request, "reports/email/report_list.html", 
                              {"domain": domain,
                               "reports": ScheduledReportFactory.get_reports()})

@login_and_domain_required
@permission_required("is_superuser")
def emailtest(request, domain, report_slug):
    """
    Test an email report 
    """
    # circular import
    from corehq.apps.reports.schedule.config import ScheduledReportFactory
    report = ScheduledReportFactory.get_report(report_slug)
    report.get_response(request.user, domain)
    return HttpResponse(report.get_response(request.user, domain))

@login_and_domain_required
@datespan_default
def report_dispatcher(request, domain, report_slug, return_json=False, map='STANDARD_REPORT_MAP', export=False):
    mapping = getattr(settings, map, None)
    if not mapping:
        return HttpResponseNotFound("Sorry, no standard reports have been configured yet.")
    for key, models in mapping.items():
        for model in models:
            klass = to_function(model)
            if klass.slug == report_slug:
                k = klass(domain, request)
                if return_json:
                    return k.as_json()
                elif export:
                    return k.as_export()
                return k.as_view()
    raise Http404

@login_and_domain_required
@datespan_default
def custom_report_dispatcher(request, domain, report_slug, export=False):
    mapping = getattr(settings, 'CUSTOM_REPORT_MAP', None)
    if not mapping or not domain in mapping:
        return HttpResponseNotFound("Sorry, no custom reports have been configured yet.")
    for model in mapping[domain]:
        klass = to_function(model)
        if klass.slug == report_slug:
            k = klass(domain, request)
            if export:
                return k.as_export()
            return k.as_view()
    raise Http404
