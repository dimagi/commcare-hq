import datetime as DT
import json
import dateutil.parser
from corehq.apps.users.util import raw_username
from dimagi.utils.web import render_to_response
from dimagi.utils.parsing import string_to_datetime
from dimagi.utils.couch.database import get_db
from collections import defaultdict
from django.http import HttpResponseRedirect, HttpResponse
from django.core.urlresolvers import reverse
from .googlecharts import get_punchcard_url
from .calc import punchcard
from corehq.apps.domain.decorators import login_and_domain_required, cls_login_and_domain_required
from corehq.apps.reports.templatetags.report_tags import render_user_inline
from dimagi.utils.couch.pagination import CouchPaginator, ReportBase

from couchexport.export import export_excel
from StringIO import StringIO
from django.contrib import messages

iso_format = '%Y-%m-%dT%H:%M:%SZ'
def format_time(time):
    return time.strftime(iso_format)
#def report_list(request, domain):
#    template = "reports/report_list.html"
#    return render_to_response(request, template, {'domain': domain})

def user_id_to_username(user_id):
    if not user_id:
        return None
    try:
        login = get_db().get(user_id)
    except:
        return None
    return raw_username(login['django_user']['username'])

@login_and_domain_required
def default(request, domain):
    return HttpResponseRedirect(reverse("submission_log_report", args=[domain]))

@login_and_domain_required
def export_data(req, domain):
    """
    Download all data for a couchdbkit model
    """
    export_tag = req.GET.get("export_tag", "")
    next = req.GET.get("next", "")
    if not next:
        next = reverse('excel_export_data_report', args=[domain])
    if not export_tag:
        raise Exception("You must specify a model to download!")
    tmp = StringIO()
    if export_excel([domain, export_tag], tmp):
        response = HttpResponse(mimetype='application/vnd.ms-excel')
        response['Content-Disposition'] = 'attachment; filename=%s.xls' % export_tag
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

        headings = ["Username", "Submit Time", "Form"]
        return render_to_response(request, template, {
            'headings': headings,
            'rows': rows,
            'ajax_source': reverse('paging_submit_history', args=[domain, individual, show_unregistered]),
        })
    def rows(self, skip, limit):
        def xmlns_to_name(xmlns):
            try:
                form = get_db().view('reports/forms_by_xmlns', key=[self.domain, xmlns], group=True).one()['value']
                lang = form['app']['langs'][0]
            except:
                form = None

            if form:
                name = "<a href='%s'>%s &gt; %s &gt; %s</a>" % (
                    reverse("corehq.apps.app_manager.views.view_app", args=[self.domain, form['app']['id']])
                    + "?m=%s&f=%s" % (form['module']['id'], form['form']['id']),
                    form['app']['name'],
                    form['module']['name'][lang],
                    form['form']['name'][lang]
                )
            else:
                name = xmlns
            return name
        def format_time(time):
            "time is an ISO timestamp"
            return time.replace('T', ' ').replace('Z', '')
        if self.individual:
            rows = get_db().view('reports/submit_history',
                endkey=[self.domain, self.individual],
                startkey=[self.domain, self.individual, {}],
                descending=True,
                reduce=False,
                skip=skip,
                limit=limit
            )
            def view_to_table(row):
                time = row['value'].get('time')
                xmlns = row['value'].get('xmlns')
                username = user_id_to_username(self.individual)

                #time = DT.datetime.strptime(time, iso_format)
                time = format_time(time)
                xmlns = xmlns_to_name(xmlns)
                return [username, time, xmlns]

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

                #time = DT.datetime.strptime(time, iso_format)
                time = format_time(time)
                xmlns = xmlns_to_name(xmlns)
                username = user_id_to_username(user_id)
                if username:
                    return [username, time, xmlns]
                elif self.show_unregistered:
                    username = '"%s" (unregistered)' % fake_name if fake_name else "(unregistered)"
                    return [username, time, xmlns]

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

    rows = []

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
        "ajax_source": reverse('paging_active_cases', args=[domain]),
    })

@login_and_domain_required
def paging_active_cases(request, domain):

    days = 31
    def get_active_cases(userid, days=days):
        since_date = DT.datetime.now() - DT.timedelta(days=days)
        r = get_db().view('case/by_last_date',
            startkey=[domain, userid, format_time(since_date)],
            endkey=[domain, userid, {}],
            group=True,
            group_level=0
        ).one()
        return r['value']['count'] if r else 0
    def get_late_cases(userid, days=days):
        EPOCH = DT.datetime(1970, 1, 1)
        since_date = DT.datetime.now() - DT.timedelta(days=days)
        DAYS = (since_date - EPOCH).days
        r = get_db().view('case/by_last_date',
            startkey=[domain, userid],
            endkey=[domain, userid, format_time(since_date)],
            group=True,
            group_level=0
        ).one()

        return (r['value']['count']*DAYS-r['value']['sum'], r['value']['count']) if r else (0,0)
    def get_forms_completed(userid, days=7):
        since_date = DT.datetime.now() - DT.timedelta(days=days)
        r = get_db().view('reports/submit_history',
            startkey=[domain, userid, format_time(since_date)],
            endkey=[domain, userid, {}],
            group=True,
            group_level=0
        ).one()
        return r['value'] if r else 0
        
    def view_to_table(row):
        keys = row['value']

        open_cases = get_db().view('case/open_cases', keys=[[domain, key] for key in keys], group=True)
        open_cases = sum(map(lambda x: x['value'], open_cases))

        active_cases = sum(map(get_active_cases, keys))

        days_late, cases_late = map(sum, zip(*map(get_late_cases, keys)))

        visits = sum(map(get_forms_completed, keys))

        assert(open_cases-active_cases == cases_late)
        return [
            user_id_to_username(keys[0]),
            "%s/%s (%d%%)" % (active_cases, open_cases,  (active_cases*100/open_cases)) if open_cases else "--",
            "%s cases" % cases_late if cases_late else "--",
            "%.1f" % (days_late/cases_late) if cases_late > 1 else "%d" % (days_late/cases_late) if cases_late \
            else "--",
            visits
        ]

    paginator = CouchPaginator(
        "users/collated_commcare_users",
        view_to_table,
        search=False,
        view_args=dict(
            startkey=[domain],
            endkey=[domain, {}],
            descending=False
        )
    )
    return paginator.get_ajax_response(request)


@login_and_domain_required
def submit_time_punchcard(request, domain):
    individual = request.GET.get("individual", '')
    data = punchcard.get_data(domain, individual)
    url = get_punchcard_url(data)
    #user_data = punchcard.get_users(domain)
#    if individual:
#        selected_user = [user for user, _ in user_data if user["_id"] == user_id][0]
#        name = "Punchcard Report for %s at %s" % (render_user_inline(selected_user))
    return render_to_response(request, "reports/punchcard.html", {
        "chart_url": url,
        #"user_data": user_data,
        #"clinic_id": clinic_id,
        #"user_id": user_id
    })

@login_and_domain_required
def user_summary(request, domain, template="reports/user_summary.html"):
    report_name = "User Summary Report (number of forms filled in by person)"

    return render_to_response(request, template, {
        "domain": domain,
        "show_dates": False,
        "report": {
            "name": report_name
        },
        "ajax_source": reverse('paging_user_summary', args=[domain]),
    })

@login_and_domain_required
def paging_user_summary(request, domain):

    def view_to_table(row):
        row['last_submission_date'] = dateutil.parser.parse(row['last_submission_date'])
        return row
    paginator = CouchPaginator(
        "reports/user_summary",
        view_to_table,
        search=False,
        view_args=dict(
            group=True,
            startkey=[domain],
            endkey=[domain, {}],
        )
    )
    return paginator.get_ajax_response(request)

@login_and_domain_required
def submission_log(request, domain):
    individual = request.GET.get('individual', '')
    show_unregistered = request.GET.get('show_unregistered', 'false')
    if individual:
        pass

    user_ids = get_db().view('reports/all_users', startkey=[domain], endkey=[domain, {}], group=True)
    user_ids = [result['key'][1] for result in user_ids]
    users = []
    for user_id in user_ids:
        username = user_id_to_username(user_id)
        if username:
            users.append({'id': user_id, 'username': username})

    return render_to_response(request, "reports/submission_log.html", {
        "domain": domain,
        "show_users": True,
        "report": {
            "name": "Submission Log",
            "header": [],
            "rows": [],
        },
        "users": users,
        "individual": individual,
        "show_unregistered": show_unregistered,
    })

@login_and_domain_required
def daily_submissions(request, domain, view_name, title):
    start_date = request.GET.get('startdate')
    end_date = request.GET.get('enddate')
    if end_date:
        end_date = DT.date(*map(int, end_date.split('-')))
    else:
        end_date = DT.datetime.utcnow().date()

    if start_date:
        start_date = DT.date(*map(int, start_date.split('-')))
    else:
        start_date = (end_date- DT.timedelta(days=6))
    results = get_db().view(
        view_name,
        group=True,
        startkey=[domain, start_date.isoformat()],
        endkey=[domain, end_date.isoformat(), {}]
    ).all()

    all_users_results = get_db().view("reports/all_users", startkey=[domain], endkey=[domain, {}], group=True).all()
    user_ids = [result['key'][1] for result in all_users_results]

    dates = [start_date]
    while dates[-1] < end_date:
        dates.append(dates[-1] + DT.timedelta(days=1))
    date_map = dict([(date.isoformat(), i+1) for (i,date) in enumerate(dates)])
    user_map = dict([(user_id, i) for (i, user_id) in enumerate(user_ids)])
    rows = [[0]*(1+len(date_map)) for _ in user_ids]
    for result in results:
        _, date, user_id = result['key']
        val = result['value']
        rows[user_map[user_id]][date_map[date]] = val
    for i,user_id in enumerate(user_ids):
        rows[i][0] = user_id_to_username(user_id)

    valid_rows = []
    for row in rows:
        if row[0]:
            valid_rows.append(row)
    rows = valid_rows
    headers = ["Username"] + dates
    return render_to_response(request, "reports/generic_report.html", {
        "domain": domain,
        "show_dates": True,
        "start_date": start_date,
        "end_date": end_date,
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

    