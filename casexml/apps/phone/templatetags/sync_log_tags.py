from django import template
from django.template.loader import render_to_string
from casexml.apps.phone.models import SyncLog

register = template.Library()

@register.simple_tag
def sync_logs_for_chw(chw_id):
    logs = SyncLog.view("phone/sync_logs_by_chw", reduce=False, startkey=[chw_id], endkey=[chw_id, {}], include_docs=True)
    return render_to_string("phone/partials/sync_log_for_chw_table.html", 
                            {"sync_data": logs})
    