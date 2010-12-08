
from dimagi.utils.web import render_to_response
from dimagi.utils.parsing import string_to_datetime
from dimagi.utils.couch.database import get_db
import dateutil.parser
import datetime as DT
from collections import defaultdict
from django.http import HttpResponseRedirect
from django.core.urlresolvers import reverse

iso_format = '%Y-%m-%dT%H:%M:%SZ'

#def report_list(request, domain):
#    template = "reports/report_list.html"
#    return render_to_response(request, template, {'domain': domain})

def default(request, domain):
    return HttpResponseRedirect(reverse("individual_summary_report", args=[domain]))

def submit_history(request, domain, template="reports/partials/couch_report_partial.html"):
    individual = request.GET.get('individual', '')
    rows = []

    if individual:
        headings = ["Submit Time", "XMLNS"]
        results = get_db().view('reports/submit_history',
            endkey=[domain, individual],
            startkey=[domain, individual, {}],
            descending=True,
        ).all()

        for result in results:
            time = result['value'].get('time')
            xmlns = result['value'].get('xmlns')

            time = DT.datetime.strptime(time, iso_format)
            rows.append([time, xmlns])
    else:
        headings = ["Username", "Submit Time", "XMLNS"]
        results = get_db().view('reports/all_submissions',
            endkey=[domain],
            startkey=[domain, {}],
            descending=True,
        ).all()
        for result in results:
            time = result['value'].get('time')
            xmlns = result['value'].get('xmlns')
            username = result['value'].get('username')

            time = DT.datetime.strptime(time, iso_format)
            rows.append([username, time, xmlns])
    return render_to_response(request, template, {
        'headings': headings,
        'rows': rows,
    })

def user_summary(request, domain):
    results = get_db().view(
        "reports/user_summary",
        group=True,
        startkey=[domain],
        endkey=[domain, {}]
    ).all()
    rows = [result['value'] for result in results]
    for row in rows:
        row['last_submission_date'] = dateutil.parser.parse(row['last_submission_date'])
    report_name = "User Summary Report (number of forms filled in by person)"

    return render_to_response(request, "reports/user_summary.html", {
        "domain": domain,
        "show_dates": False,
        "report": {
            "name": report_name,
            "rows": rows,
        }
    })

def individual_summary(request, domain):
    individual = request.GET.get('individual', '')
    if individual:
        pass

    usernames = get_db().view('reports/all_users', startkey=[domain], endkey=[domain, {}], group=True)
    usernames = [result['key'][1] for result in usernames]
    return render_to_response(request, "reports/individual_summary.html", {
        "domain": domain,
        "show_users": True,
        "report": {
            "name": "Individual Summary",
            "header": [],
            "rows": [],
        },
        "usernames": usernames,
        "individual": individual,
    })

def daily_submissions(request, domain, view_name):
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
        endkey=[domain, end_date.isoformat()]
    ).all()
    all_users_results = get_db().view("reports/all_users", startkey=[domain], endkey=[domain, {}], group=True).all()
    usernames = [result['key'][1] for result in all_users_results]

    dates = [start_date]
    while dates[-1] < end_date:
        dates.append(dates[-1] + DT.timedelta(days=1))
    date_map = dict([(date.isoformat(), i+1) for (i,date) in enumerate(dates)])
    username_map = dict([(username, i) for (i, username) in enumerate(usernames)])
    rows = [[0]*(1+len(date_map)) for _ in usernames]
    for result in results:
        _, date, username = result['key']
        val = result['value']
        rows[username_map[username]][date_map[date]] = val
    for i,username in enumerate(usernames):
        rows[i][0] = username

    headers = ["Username"] + dates
    print "end date: %s" % end_date
    return render_to_response(request, "reports/daily_submissions.html", {
        "domain": domain,
        "show_dates": True,
        "start_date": start_date,
        "end_date": end_date,
        "report": {
            "name": "Daily Submissions by User",
            "headers": headers,
            "rows": rows,
        }
    })

    