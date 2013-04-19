from django import template
import pytz
from django.utils.html import escape
from django.utils.translation import ugettext as _
from couchforms.models import XFormInstance
from dimagi.utils.timezones import utils as tz_utils
from couchdbkit.exceptions import ResourceNotFound

SYSTEM_FIELD_NAMES = (
    "drugs_prescribed", "case", "meta", "clinic_ids", "drug_drill_down", "tmp",
    "info_hack_done"
)

register = template.Library()


@register.simple_tag
def render_form_xml(form):
    return '<pre class="fancy-code prettyprint linenums"><code class="language-xml">%s</code></pre>' % escape(form.get_xml().replace("><", ">\n<"))


@register.simple_tag
def form_inline_display(form_id, timezone=pytz.utc):
    if form_id:
        try:
            form = XFormInstance.get(form_id)
            if form:
                return "%s: %s" % (tz_utils.adjust_datetime_to_timezone\
                                   (form.received_on, pytz.utc.zone, timezone.zone).date(), 
                                   form.xmlns)
        except ResourceNotFound:
            pass
        return "%s: %s" % (_("missing form"), form_id)
    return _("empty form id found")
