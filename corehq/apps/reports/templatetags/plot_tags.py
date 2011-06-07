from django import template
from django.template.loader import render_to_string
from corehq.apps.reports.flot import get_cumulative_counts, get_sparkline_totals
from dimagi.utils.parsing import string_to_datetime
from dimagi.utils.couch.database import get_db
from corehq.apps.reports.calc import entrytimes
import json

register = template.Library()

@register.simple_tag
def case_plot_js(chw_id):
    # there has to be a better way to do this
    data = get_db().view("phone/cases_sent_to_chws", group=True, group_level=2, reduce=True, 
                             startkey=[chw_id], endkey=[chw_id, {}])
    daily_case_data, total_case_data = get_cumulative_counts([string_to_datetime(row["value"]).date() for row in data])
    return render_to_string("reports/partials/case_plot.js",
                            {"daily_case_data": daily_case_data,
                             "total_case_data": total_case_data})
    
@register.simple_tag
def formentry_plot_js(domain, user_id):
    data = entrytimes.get_data(domain, user_id)
    totals, avgs = get_sparkline_totals(data)
    
    def _tot_to_flot(k, v):
        return {"label": "%s (total)" % k, "data": v, "yaxis": 2,
                "points": { "show": True }}
    
    def _avg_to_flot(k, v):
        return {"label": "%s (average time)" % k, "data": v,
                "lines": { "show": True }, "points": { "show": True }}
    
    plots = dict((k, {"totals": _tot_to_flot(k,v)}) for k, v in totals.items())
    for k, v in avgs.items():
        plots[k]["averages"] = _avg_to_flot(k,v)
    
    return render_to_string("reports/partials/formentry_plot.js",
                            {"plot_data": json.dumps(plots)}) 
                               


