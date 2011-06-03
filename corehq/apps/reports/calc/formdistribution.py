from collections import defaultdict
from dimagi.utils.couch.database import get_db

def get_chart_data(domain, user=None):
    """
    Get data, suitable for a pie chart
    """
    # todo: this doesn't below in views
    from corehq.apps.reports.views import xmlns_to_name
    
    data = []
    startkey = ["u", domain, user] if user else ["d", domain]
    endkey = ["u", domain, user, {}] if user else ["d", domain, {}]
    view = get_db().view("formtrends/form_type_by_user", 
                         startkey=startkey,
                         endkey=endkey,
                         group=True,
                         reduce=True)
    for row in view:
        xmlns = row["key"][-1]
        form_name = xmlns_to_name(xmlns, domain) 
        data.append({"display": form_name,
                     "value": row["value"],
                     "description": "(%s) submissions of %s" % \
                                (row["value"], form_name)})
        
    return data