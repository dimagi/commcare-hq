from django import template
from django.template.loader import render_to_string
from corehq.apps.reports.flot import get_cumulative_counts, get_sparkline_json,\
    get_sparkline_extras
from dimagi.utils.parsing import string_to_datetime
from dimagi.utils.couch.database import get_db
from corehq.apps.reports.calc import entrytimes

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
def formentry_plot_js(clinic_id, user_id):
    # there has to be a better way to do this
    data = entrytimes.get_data(clinic_id, user_id)
    totals_json, avgs_json = get_sparkline_json(data)
    return render_to_string("reports/partials/formentry_plot.js",
                              {"avgs_data": avgs_json,
                               "totals_data": totals_json,
                               "chart_extras": get_sparkline_extras(data)})

