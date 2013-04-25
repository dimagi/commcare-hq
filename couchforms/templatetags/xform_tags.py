from functools import partial
import copy

from django.template.loader import render_to_string
from django.core.urlresolvers import reverse
from django import template
import pytz
from django.utils.html import escape
from django.utils.translation import ugettext as _
from couchforms.models import XFormInstance
from dimagi.utils.timezones import utils as tz_utils
from couchdbkit.exceptions import ResourceNotFound

from casexml.apps.case.xform import extract_case_blocks
from casexml.apps.case import const
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.templatetags.case_tags import case_inline_display


from corehq.apps.hqwebapp.templatetags.proptable_tags import (
    get_tables_as_columns, get_definition)


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


def sorted_case_update_keys(keys):
    """Put common @ attributes at the bottom"""
    def mycmp(x, y):
        if x[0] == '@' and y[0] == '@':
            return cmp(x, y)
        if x[0] == '@':
            return 1
        if y[0] == '@':
            return -1
        return cmp(x, y)
    return sorted(keys, cmp=mycmp)


def sorted_form_metadata_keys(keys):
    def mycmp(x, y):
        foo = ('timeStart', 'timeEnd')
        bar = ('username', 'userID')
        if x in foo and y in foo:
            return -1 if foo.index(x) == 0 else 1
        elif x in foo or y in foo:
            return 0

        if x in bar and y in bar:
            return -1 if bar.index(x) == 0 else 1
        elif x in bar and y in bar:
            return 0

        return cmp(x, y)
    return sorted(keys, cmp=mycmp)


def form_key_filter(key):
    if key in SYSTEM_FIELD_NAMES:
        return False

    if any(key.startswith(p) for p in ['#', '@', '_']):
        return False

    return True


@register.simple_tag
def render_form(form, domain, options):
    """
    Uses options since Django 1.3 doesn't seem to support templatetag kwargs.
    Change to kwargs when we're on a version of Django that does.
    
    """
    timezone = options.get('timezone', pytz.utc)
    #display = options.get('display')
    case_id = options.get('case_id')

    case_id_attr = "@%s" % const.CASE_TAG_ID

    _get_tables_as_columns = partial(get_tables_as_columns, timezone=timezone)

    # Form Data tab. deepcopy to ensure that if top_level_tags() returns live
    # references we don't change any data.
    form_dict = copy.deepcopy(form.top_level_tags())
    form_dict.pop('change', None)  # this data already in Case Changes tab
    form_keys = [k for k in form_dict.keys() if form_key_filter(k)]
    form_data = _get_tables_as_columns(form_dict, get_definition(form_keys))

    # Case Changes tab
    case_blocks = extract_case_blocks(form)
    for i, block in enumerate(list(case_blocks)):
        if case_id and block.get(case_id_attr) == case_id:
            case_blocks.pop(i)
            case_blocks.insert(0, block)

    cases = []
    for b in case_blocks:
        this_case_id = b.get(case_id_attr)
        this_case = CommCareCase.get(this_case_id) if this_case_id else None

        if this_case and this_case._id:
            url = reverse('case_details', args=[domain, this_case._id])
        else:
            url = "#"

        definition = get_definition(sorted_case_update_keys(b.keys()))
        cases.append({
            "is_current_case": case_id and this_case_id == case_id,
            "name": case_inline_display(this_case),
            "table": _get_tables_as_columns(b, definition),
            "url": url
        })

    # Form Metadata tab
    meta = form_dict.pop('meta')
    definition = get_definition(sorted_form_metadata_keys(meta.keys()))
    form_meta_data = _get_tables_as_columns(meta, definition)

    return render_to_string("form/partials/single_form.html", {
        "context_case_id": case_id,
        "instance": form,
        "is_archived": form.doc_type == "XFormArchived",
        "domain": domain,
        "form_data": form_data,
        "cases": cases,
        "form_table_options": {
            # todo: wells if display config has more than one column
            "put_loners_in_wells": False
        },
        "form_meta_data": form_meta_data,
    })


