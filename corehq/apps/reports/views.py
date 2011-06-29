from collections import defaultdict
from datetime import datetime, timedelta, date
import json
from corehq.apps.reports.case_activity import CaseActivity
from corehq.apps.users.export import export_users
from corehq.apps.users.models import CouchUser
from corehq.apps.users.util import user_id_to_username
from couchforms.models import XFormInstance
from dimagi.utils.couch.loosechange import parse_date
from dimagi.utils.export import CsvWorkBook
from dimagi.utils.web import json_response, json_request, render_to_response
from dimagi.utils.couch.database import get_db
from django.http import HttpResponseRedirect, HttpResponse, HttpResponseBadRequest
from django.core.urlresolvers import reverse
from .googlecharts import get_punchcard_url
from .calc import punchcard
from corehq.apps.domain.decorators import login_and_domain_required
from dimagi.utils.couch.pagination import CouchPaginator, ReportBase
import couchforms.views as couchforms_views
from couchexport.export import export, Format
from StringIO import StringIO
from django.contrib import messages
from dimagi.utils.parsing import json_format_datetime
from django.contrib.auth.decorators import permission_required
from dimagi.utils.decorators.datespan import datespan_in_request
from dimagi.utils.dates import DateSpan
from corehq.apps.reports.calc import formdistribution, entrytimes
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.export import export_cases_and_referrals
from django.template.defaultfilters import yesno
from casexml.apps.case.xform import extract_case_blocks
from corehq.apps.reports.display import xmlns_to_name
import sys

#def report_list(request, domain):
#    template = "reports/report_list.html"
#    return render_to_response(request, template, {'domain': domain})

DATE_FORMAT = "%Y-%m-%d"

@login_and_domain_required
def default(request, domain):
    return HttpResponseRedirect(reverse("submission_log_report", args=[domain]))

@login_and_domain_required
def export_data(req, domain):
    """
    Download all data for a couchdbkit model
    """
    try:
        export_tag = json.loads(req.GET.get("export_tag", "null") or "null")
    except ValueError:
        return HttpResponseBadRequest()

    format = req.GET.get("format", Format.XLS_2007)
    next = req.GET.get("next", "")
    if not next:
        next = reverse('excel_export_data_report', args=[domain])
    tmp = StringIO()
    if export([domain, export_tag], tmp, format=format):
        response = HttpResponse(mimetype='application/vnd.ms-excel')
        response['Content-Disposition'] = 'attachment; filename=%s.%s' % (export_tag, format)
        response.write(tmp.getvalue())
        tmp.close()
        return response
    else:
        messages.error(req, "Sorry, there was no data found for the tag '%s'." % export_tag)
        return HttpResponseRedirect(next)


class SubmitHistory(ReportBase):
    def __init__(self, request, domain, individual, show_unregistered="false"):
        self.request = request
        self.domain = domain
        self.individual = individual
        self.show_unregistered = True #json.loads(show_unregistered)

    @classmethod
    def view(cls, request, domain, template="reports/partials/couch_report_partial.html"):

        individual = request.GET.get('individual', '')
        show_unregistered = request.GET.get('show_unregistered', 'false')
        rows = []

        headings = ["View Form", "Username", "Submit Time", "Form"]
        return render_to_response(request, template, {
            'headings': headings,
            'rows': rows,
            'ajax_source': reverse('paging_submit_history', args=[domain, individual, show_unregistered]),
        })
    def rows(self, skip, limit):
        def format_time(time):
            "time is an ISO timestamp"
            return time.replace('T', ' ').replace('Z', '')
        def form_data_link(instance_id):
            return "<a class='ajax_dialog' href='%s'>View Form</a>" % reverse('render_form_data', args=[self.domain, instance_id])
        if self.individual:
            rows = get_db().view('reports/submit_history',
                endkey=[self.domain, self.individual],
                startkey=[self.domain, self.individual, {}],
                descending=True,
                reduce=False,
                skip=skip,
                limit=limit,
            )
            def view_to_table(row):
                time = row['value'].get('time')
                xmlns = row['value'].get('xmlns')
                username = user_id_to_username(self.individual)

                time = format_time(time)
                xmlns = xmlns_to_name(xmlns, self.domain, html=True)
                return [form_data_link(row['id']), username, time, xmlns]

        else:
            rows = get_db().view('reports/all_submissions',
                endkey=[self.domain],
                startkey=[self.domain, {}],
                descending=True,
                reduce=False,
                skip=skip,
                limit=limit,
            )
            def view_to_table(row):
                time = row['value'].get('time')
                xmlns = row['value'].get('xmlns')
                user_id = row['value'].get('user_id')
                fake_name = row['value'].get('username')

                time = format_time(time)
                xmlns = xmlns_to_name(xmlns, self.domain, html=True)
                username = user_id_to_username(user_id)
                if username:
                    return [form_data_link(row['id']), username, time, xmlns]
                elif self.show_unregistered:
                    username = '"%s" (unregistered)' % fake_name if fake_name else "(unregistered)"
                    return [form_data_link(row['id']), username, time, xmlns]

        return [view_to_table(row) for row in rows]
    def count(self):
        try:
            if self.individual:
                return get_db().view('reports/submit_history',
                    startkey=[self.domain, self.individual],
                    endkey=[self.domain, self.individual, {}],
                    group=True,
                    group_level=2
                ).one()['value']
            else:
                return get_db().view('reports/all_submissions',
                    startkey=[self.domain],
                    endkey=[self.domain, {}],
                    group=True,
                    group_level=1
                ).one()['value']
        except TypeError:
            return 0

@login_and_domain_required
def active_cases(request, domain):

    rows = get_active_cases_json(domain, **json_request(request.GET))

    headings = ["Username", "Active/Open Cases (%)", "Late Cases", "Average Days Late", "Visits Last Week"
        #"Open Referrals", "Active Referrals"
    ]

    return render_to_response(request, "reports/generic_report.html", {
        "domain": domain,
        "report": {
            "name": "Case Activity",
            "headers": headings,
            "rows": rows,
        },
    })

def get_active_cases_json(domain, days=31, **kwargs):
    users = CouchUser.commcare_users_by_domain(domain)
    def get_active_cases(userid, days=days):
        since_date = datetime.utcnow() - timedelta(days=days)
        r = get_db().view('case/by_last_date',
            startkey=[domain, userid, json_format_datetime(since_date)],
            endkey=[domain, userid, {}],
            group=True,
            group_level=0
        ).one()
        return r['value']['count'] if r else 0
    def get_late_cases(userid, days=days):
        EPOCH = datetime(1970, 1, 1)
        since_date = datetime.utcnow() - timedelta(days=days)
        DAYS = (since_date - EPOCH).days
        r = get_db().view('case/by_last_date',
            startkey=[domain, userid],
            endkey=[domain, userid, json_format_datetime(since_date)],
            group=True,
            group_level=0
        ).one()

        return (r['value']['count']*DAYS-r['value']['sum'], r['value']['count']) if r else (0,0)
    def get_forms_completed(userid, days=7):
        since_date = datetime.utcnow() - timedelta(days=days)
        r = get_db().view('reports/submit_history',
            startkey=[domain, userid, json_format_datetime(since_date)],
            endkey=[domain, userid, {}],
            group=True,
            group_level=0
        ).one()
        return r['value'] if r else 0

    def get_open_cases(userID):
        open_cases = get_db().view('hqcase/open_cases', key=[domain, userID], group=True).one()
        open_cases = open_cases['value'] if open_cases else 0
        return open_cases


    def user_to_row(user):
        userID = user.userID

        open_cases = get_open_cases(userID)
        active_cases = get_active_cases(userID)

        days_late, cases_late = get_late_cases(userID)

        visits = get_forms_completed(userID)

        assert(open_cases-active_cases == cases_late)
        return [
            user.raw_username,
            "%s/%s (%d%%)" % (active_cases, open_cases,  (active_cases*100/open_cases)) if open_cases else "--",
            "%s cases" % cases_late if cases_late else "--",
            "%.1f" % (days_late/cases_late) if cases_late > 1 else "%d" % (days_late/cases_late) if cases_late \
            else "--",
            visits
        ]


    return sorted([user_to_row(user) for user in users])

@login_and_domain_required
def case_activity(request, domain):
    params = json_request(request.GET)
    display = params.get('display', ['percent'])
    userIDs = params.get('userIDs') or [user.userID for user in CouchUser.commcare_users_by_domain(domain)]
    userIDs.sort(key=lambda userID: user_id_to_username(userID))
    landmarks = [timedelta(days=l) for l in params.get('landmarks') or [7,30,90]]
    landmarks.append(None)
    now = datetime.utcnow()
    report = CaseActivity(domain, userIDs, landmarks, now)
    data = report.get_data()
    headers = ["User"] + ["Last %s Days" % l.days if l else "Ever" for l in landmarks]
    rows = []

    extra = {}

    for userID in data:
        extra[userID] = []
        for i in range(len(landmarks)):
            next = data[userID][i+1] if i+1 < len(landmarks) else None
            last = data[userID][i-1] if i else 0
            current = data[userID][i]
            extra[userID].append({
                "total": current,
                "diff": current - last,
                "next": next,
                "last": last,
                "percent": 1.0*current/next if next else None
            })

    def user_id_link(user_id):
        template = '<a href="%(link)s?individual=%(user_id)s">%(username)s</a>'
        return template % {"link": reverse("case_list_report", args=[domain]),
                           "user_id": user_id,
                           "username": user_id_to_username(userID)} 
    for userID in extra:
        
        row = [user_id_link(userID)]
        for entry in extra[userID]:
            if entry['total'] == entry['diff'] or 'diff' not in display:
                fmt = "{total}"
            else:
                fmt = "+ {diff} = {total}"
                
            if entry['percent'] and 'percent' in display:
                fmt += " ({percent:.0%} of {next})"
            formatted = fmt.format(**entry)
            try:
                formatted = int(formatted)
            except ValueError:
                pass
            row.append(formatted)
        rows.append(row)
    return render_to_response(request, "reports/generic_report.html", {
        "domain": domain,
        "report": {
            "name": "Case Activity",
            "headers": headers,
            "rows": rows,
        },
    })

def _user_list(domain):
    user_ids = get_db().view('submituserlist/all_users', startkey=[domain], endkey=[domain, {}], group=True)
    user_ids = [result['key'][1] for result in user_ids]
    users = []
    for user_id in user_ids:
        username = user_id_to_username(user_id)
        if username:
            users.append({'id': user_id, 'username': username})
    users.sort(key=lambda user: user['username'])
    return users

def _form_list(domain):
    view = get_db().view("formtrends/form_duration_by_user", 
                         startkey=["xdu", domain, ""],
                         endkey=["xdu", domain, {}],
                         group=True,
                         group_level=3,
                         reduce=True)
    return [{"display": xmlns_to_name(r["key"][2], domain), "xmlns": r["key"][2]} for r in view]
    
@login_and_domain_required
@datespan_in_request(from_param="startdate", to_param="enddate", 
                     format_string=DATE_FORMAT, default_days=7)
def completion_times(request, domain):
    headers = ["User", "Average duration", "Shortest", "Longest", "# Forms"]
    form = request.GET.get('form', '')
    rows = []
    if form:
        data = entrytimes.get_user_data(domain, form, request.datespan)
        totalsum = totalcount = 0
        def to_minutes(val_in_ms):
            return timedelta(milliseconds=float(val_in_ms))
        
        globalmin = sys.maxint
        globalmax = 0
        for user_id, datadict in data.items():
            rows.append([user_id_to_username(user_id),
                         to_minutes(float(datadict["sum"]) / float(datadict["count"])),
                         to_minutes(datadict["min"]),
                         to_minutes(datadict["max"]),
                         datadict["count"]
                         ])
            totalsum = totalsum + datadict["sum"]
            totalcount = totalcount + datadict["count"]
            globalmin = min(globalmin, datadict["min"])
            globalmax = max(globalmax, datadict["max"])
        rows.insert(0, ["-- Total --", 
                        to_minutes(float(totalsum)/float(totalcount)),
                        to_minutes(globalmin),
                        to_minutes(globalmax),
                        totalcount])
    
    return render_to_response(request, "reports/generic_report.html", {
        "domain": domain,
        "show_forms": True,
        "selected_form": form,
        "forms": _form_list(domain),
        "show_dates": True,
        "datespan": request.datespan,
        "report": {
            "name": "Completion Times",
            "headers": headers,
            "rows": rows,
        },
    })
    

@login_and_domain_required
def case_list(request, domain):
    headers = ["Name", "User", "Created Date", "Modified Date", "Status"]
    individual = request.GET.get('individual', '')
    return render_to_response(request, "reports/generic_report.html", {
        "domain": domain,
        "show_users": True,
        "report": {
            "name": "Case List",
            "headers": headers,
            "rows": [],
        },
        "users": _user_list(domain),
        "ajax_source": reverse('paging_case_list', args=[domain, individual]),
        "individual": individual,
    })
    
@login_and_domain_required
def paging_case_list(request, domain, individual):
    def view_to_table(row):
        def date_to_json(date):
            return date.strftime('%Y-%m-%d %H:%M:%S') if date else "",
        
        def case_data_link(case_id, case_name):
            return "<a class='ajax_dialog' href='%s'>%s</a>" % \
                    (reverse('case_details', args=[domain, case_id]),
                     case_name)
        
        case = CommCareCase.wrap(row["doc"])
        return [case_data_link(row['id'], case.name), 
                user_id_to_username(case.user_id), 
                date_to_json(case.opened_on), 
                date_to_json(case.modified_on),
                yesno(case.closed, "closed,open") ]
    
    if individual:
        startkey = [domain, individual]
        endkey = [domain, individual, {}]
    else: 
        startkey = [domain]
        endkey = [domain, {}]
    paginator = CouchPaginator(
        "hqcase/all_cases",
        view_to_table,
        search=False,
        view_args=dict(
            reduce=False,
            include_docs=True,
            # this is horrible, but the paginator currently automatically
            # adds descending=True so we have to swap these.
            startkey=endkey,
            endkey=startkey,
        )
    )
    return paginator.get_ajax_response(request)

@login_and_domain_required
def case_details(request, domain, case_id):
    return render_to_response(request, "reports/case_details.html", {
        "domain": domain,
        "case_id": case_id,
        "report": {
            "name": "Case Details"
        }
    })

@login_and_domain_required
def download_cases(request, domain):
    cases = CommCareCase.view('hqcase/open_cases', startkey=[domain], endkey=[domain, {}], reduce=False, include_docs=True)
    users = CouchUser.commcare_users_by_domain(domain)

    workbook = CsvWorkBook()
    export_cases_and_referrals(cases, workbook)
    export_users(users, workbook)
    response = HttpResponse(workbook.to_zip())
    response['Content-Type'] = "application/zip"
    response['Content-Disposition'] = "attachment; filename=Cases.zip"
    return response

@login_and_domain_required
def submit_time_punchcard(request, domain):
    individual = request.GET.get("individual", '')
    data = punchcard.get_data(domain, individual)
    url = get_punchcard_url(data)
    return render_to_response(request, "reports/partials/punchcard.html", {
        "chart_url": url,
    })

@login_and_domain_required
def submit_trends(request, domain):
    individual = request.GET.get("individual", '')
    return render_to_response(request, "reports/partials/formtrends.html", 
                              {"domain": domain,
                               "user_id": individual})

@login_and_domain_required
def submit_distribution(request, domain):
    individual = request.GET.get("individual", '')
    return render_to_response(request, "reports/partials/generic_piechart.html", 
                              {"chart_data": formdistribution.get_chart_data(domain, individual),
                               "user_id": individual,
                               "graph_width": 900,
                               "graph_height": 500})

@login_and_domain_required
def submission_log(request, domain):
    individual = request.GET.get('individual', '')
    show_unregistered = request.GET.get('show_unregistered', 'false')
    
    return render_to_response(request, "reports/submission_log.html", {
        "domain": domain,
        "show_users": True,
        "report": {
            "name": "Submission Log",
            "header": [],
            "rows": [],
        },
        "users": _user_list(domain),
        "individual": individual,
        "show_unregistered": show_unregistered,
    })


@login_and_domain_required
@datespan_in_request(from_param="startdate", to_param="enddate", 
                     format_string=DATE_FORMAT, default_days=7)
def daily_submissions(request, domain, view_name, title):
    if not request.datespan.is_valid():
        messages.error(request, "Sorry, that's not a valid date range because: %s" % \
                       request.datespan.get_validation_reason())
        request.datespan = DateSpan.since(7, format="%Y-%m-%d")
    
    results = get_db().view(
        view_name,
        group=True,
        startkey=[domain, request.datespan.startdate.isoformat()],
        endkey=[domain, request.datespan.enddate.isoformat(), {}]
    ).all()
    
    all_users_results = get_db().view("submituserlist/all_users", startkey=[domain], endkey=[domain, {}], group=True).all()
    user_ids = [result['key'][1] for result in all_users_results]
    dates = [request.datespan.startdate]
    while dates[-1] < request.datespan.enddate:
        dates.append(dates[-1] + timedelta(days=1))
    date_map = dict([(date.strftime(DATE_FORMAT), i+1) for (i,date) in enumerate(dates)])
    user_map = dict([(user_id, i) for (i, user_id) in enumerate(user_ids)])
    rows = [[0]*(1+len(date_map)) for i in range(len(user_ids) + 1)]
    for result in results:
        _, date, user_id = result['key']
        val = result['value']
        if user_id in user_map:
            rows[user_map[user_id]][date_map[date]] = val
        else:
            rows[-1][date_map[date]] = val # use the last row for unknown data
            rows[-1][0] = "UNKNOWN USER" # use the last row for unknown data
    for i,user_id in enumerate(user_ids):
        rows[i][0] = user_id_to_username(user_id)

    valid_rows = []
    for row in rows:
        # include submissions from unknown/empty users that have them
        if row[0] or sum(row[1:]):
            valid_rows.append(row)
    rows = valid_rows
    headers = ["Username"] + [d.strftime(DATE_FORMAT) for d in dates]
    return render_to_response(request, "reports/generic_report.html", {
        "domain": domain,
        "show_dates": True,
        "datespan": request.datespan,
        "report": {
            "name": title,
            "headers": headers,
            "rows": rows,
        }
    })

@login_and_domain_required
def excel_export_data(request, domain, template="reports/excel_export_data.html"):
    forms = get_db().view('reports/forms_by_xmlns', startkey=[domain], endkey=[domain, {}], group=True)
    forms = [x['value'] for x in forms]

    forms = sorted(forms, key=lambda form: \
        (0, form['app']['name'], form['module']['id'], form['form']['id']) \
        if 'app' in form else \
        (1, form['xmlns'])
    )

    apps = []
    unknown_forms = []

    # organize forms into apps, modules, forms:
    #        apps = [
    #            {
    #                "name": "App",
    #                "modules": [
    #                    {
    #                        "name": "Module 1",
    #                        "id": 1,
    #                        "forms": [
    #                            {...}
    #                        ]
    #                    }
    #                ]
    #
    #            }
    #        ]

    for f in forms:
        if 'app' in f:
            if apps and f['app']['name'] == apps[-1]['name']:
                if f['module']['id'] == apps[-1]['modules'][-1]['id']:
                    apps[-1]['modules'][-1]['forms'].append(f)
                else:
                    module = f['module'].copy()
                    module.update(forms=[f])
                    apps[-1]['modules'].append(module)
            else:
                app = f['app'].copy()
                module = f['module'].copy()
                module.update(forms=[f])
                app.update(modules=[module])
                apps.append(app)

        else:
            unknown_forms.append(f)


    return render_to_response(request, template, {
        "domain": domain,
        "forms": forms,
        "forms_by_app": apps,
        "unknown_forms": unknown_forms,
        "report": {
            "name": "Export Data to Excel"
        }
    })

@login_and_domain_required
def form_data(request, domain, instance_id):
    instance = XFormInstance.get(instance_id)
    assert(domain == instance.domain)
    return render_to_response(request, "reports/form_data.html", 
                              dict(domain=domain,instance=instance,
                                   caseblocks=extract_case_blocks(instance)))

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

#Document.__repr__ = lambda self: repr(self.to_json())

@login_and_domain_required
def submissions_by_form(request, domain):
    users = CouchUser.commcare_users_by_domain(domain)
    userIDs = [user.userID for user in users]
    counts = submissions_by_form_json(domain=domain, userIDs=userIDs, **json_request(request.GET))
    form_types = _relevant_form_types(domain=domain, userIDs=userIDs, **json_request(request.GET))
    form_names = [xmlns_to_name(xmlns, domain) for xmlns in form_types]
    form_names = [name.replace("/", " / ") for name in form_names]

    if form_types:
        # this fails if form_names, form_types is [], []
        form_names, form_types = zip(*sorted(zip(form_names, form_types)))

    rows = []
    totals_by_form = defaultdict(int)

    for user in users:
        row = []
        for form_type in form_types:
            userID = user.userID
            try:
                count = counts[userID][form_type]
                row.append(count)
                totals_by_form[form_type] += count
            except:
                row.append(0)
        rows.append([user.raw_username] + row + ["* %s" % sum(row)])

    totals_by_form = [totals_by_form[form_type] for form_type in form_types]
    
    rows.append(["* All Users"] + ["* %s" % t for t in totals_by_form] + ["* %s" % sum(totals_by_form)])
    report = {
        "name": "Submissions by Form (in the last 7 days)",
        "headers": ['User'] + list(form_names) + ['All Forms'],
        "rows": rows,
    }
    return render_to_response(request, 'reports/generic_report.html', {
        "domain": domain,
        "report": report,
    })


def _relevant_form_types(domain, userIDs=None, start=None, end=None):
    start, end = mk_date_range(start, end, iso=True)
    submissions = XFormInstance.view('reports/all_submissions',
        startkey=[domain, start],
        endkey=[domain, end],
        include_docs=True,
        reduce=False
    )
    form_types = set()
    for submission in submissions:
        try:
            xmlns = submission['xmlns']
        except KeyError:
            xmlns = None
        if userIDs is not None:
            try:
                userID = submission['form']['meta']['userID']
                if userID in userIDs:
                    form_types.add(xmlns)
            except:
                pass
        else:
            form_types.add(xmlns)

    return sorted(form_types)

def submissions_by_form_json(domain, start=None, end=None, userIDs=None):
    start, end = mk_date_range(start, end, iso=True)
    submissions = XFormInstance.view('reports/all_submissions',
        startkey=[domain, start],
        endkey=[domain, end],
        include_docs=True,
        reduce=False
    )
    counts = defaultdict(lambda: defaultdict(int))
    for sub in submissions:
        try:
            userID = sub['form']['meta']['userID']
            if (userIDs is None) or (userID in userIDs):
                counts[userID][sub['xmlns']] += 1
        except:
            # if a form don't even have a userID, don't even bother tryin'
            pass
    return counts

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
    