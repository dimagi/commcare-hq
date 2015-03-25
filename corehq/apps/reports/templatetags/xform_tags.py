from functools import partial
from django.conf import settings

from django.template.loader import render_to_string
from django.core.urlresolvers import reverse
from django import template
import pytz
from django.utils.html import escape
from django.utils.translation import ugettext as _
from couchdbkit.exceptions import ResourceNotFound
from corehq import privileges
from corehq.apps.hqwebapp.templatetags.hq_shared_tags import toggle_enabled

from corehq.apps.receiverwrapper.auth import AuthContext
from corehq.apps.hqwebapp.doc_info import get_doc_info_by_id, DocInfo
from corehq.apps.reports.formdetails.readable import get_readable_data_for_submission
from corehq import toggles
from corehq.util.timezones.conversions import ServerTime
from couchforms.models import XFormInstance
from corehq.util.timezones import utils as tz_utils
from casexml.apps.case.xform import extract_case_blocks
from casexml.apps.case import const
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.templatetags.case_tags import case_inline_display
from corehq.apps.hqwebapp.templatetags.proptable_tags import (
    get_tables_as_columns, get_definition)
from django_prbac.utils import has_privilege


register = template.Library()


@register.simple_tag
def render_form_xml(form):
    xml = form.get_xml() or ''
    return '<pre class="fancy-code prettyprint linenums"><code class="language-xml">%s</code></pre>' % escape(xml.replace("><", ">\n<"))


@register.simple_tag
def form_inline_display(form_id, timezone=pytz.utc):
    if form_id:
        try:
            form = XFormInstance.get(form_id)
            if form:
                return "%s: %s" % (ServerTime(form.received_on).user_time(timezone).done().date(), form.xmlns)
        except ResourceNotFound:
            pass
        return "%s: %s" % (_("missing form"), form_id)
    return _("empty form id found")


def sorted_case_update_keys(keys):
    """Put common @ attributes at the bottom"""
    return sorted(keys, key=lambda k: (k[0] == '@', k))


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


@register.simple_tag
def render_form(form, domain, options):
    """
    Uses options since Django 1.3 doesn't seem to support templatetag kwargs.
    Change to kwargs when we're on a version of Django that does.
    
    """
    # don't actually use the passed in timezone since we assume form submissions already come
    # in in local time.
    # todo: we should revisit this when we properly handle timezones in form processing.
    timezone = pytz.utc
    case_id = options.get('case_id')
    side_pane = options.get('side_pane', False)
    user = options.get('user', None)
    case_id_attr = "@%s" % const.CASE_TAG_ID

    _get_tables_as_columns = partial(get_tables_as_columns, timezone=timezone)

    # Form Data tab
    form_data, question_list_not_found = get_readable_data_for_submission(form)

    # Case Changes tab
    case_blocks = extract_case_blocks(form)
    for i, block in enumerate(list(case_blocks)):
        if case_id and block.get(case_id_attr) == case_id:
            case_blocks.pop(i)
            case_blocks.insert(0, block)

    cases = []
    for b in case_blocks:
        this_case_id = b.get(case_id_attr)
        try:
            this_case = CommCareCase.get(this_case_id) if this_case_id else None
            valid_case = True
        except ResourceNotFound:
            this_case = None
            valid_case = False

        if this_case and this_case._id:
            url = reverse('case_details', args=[domain, this_case._id])
        else:
            url = "#"

        definition = get_definition(sorted_case_update_keys(b.keys()))
        cases.append({
            "is_current_case": case_id and this_case_id == case_id,
            "name": case_inline_display(this_case),
            "table": _get_tables_as_columns(b, definition),
            "url": url,
            "valid_case": valid_case
        })

    # Form Metadata tab
    meta = form.top_level_tags().get('meta', None) or {}
    definition = get_definition(sorted_form_metadata_keys(meta.keys()))
    form_meta_data = _get_tables_as_columns(meta, definition)
    if 'auth_context' in form:
        auth_context = AuthContext(form.auth_context)
        auth_context_user_id = auth_context.user_id
        auth_user_info = get_doc_info_by_id(domain, auth_context_user_id)
    else:
        auth_user_info = get_doc_info_by_id(domain, None)
        auth_context = AuthContext(
            user_id=None,
            authenticated=False,
            domain=domain,
        )
    meta_userID = meta.get('userID')
    meta_username = meta.get('username')
    if meta_userID == 'demo_user':
        user_info = DocInfo(
            domain=domain,
            display='demo_user',
        )
    elif meta_username == 'admin':
        user_info = DocInfo(
            domain=domain,
            display='admin',
        )
    else:
        user_info = get_doc_info_by_id(domain, meta_userID)

    edit_session_data = {'user_id': meta_userID}
    if len(case_blocks) == 1 and case_blocks[0].get(case_id_attr):
        edit_session_data["case_id"] = case_blocks[0].get(case_id_attr)

    request = options.get('request', None)
    user_can_edit = (
        request and user and request.domain
        and (user.can_edit_data() or user.is_commcare_user())
    )
    show_edit_submission = (
        user_can_edit
        and has_privilege(request, privileges.CLOUDCARE)
        and toggle_enabled(request, toggles.EDIT_SUBMISSIONS)
    )
    # stuffing this in the same flag as case rebuild
    show_resave = (
        user_can_edit and toggle_enabled(request, toggles.CASE_REBUILD)
    )
    return render_to_string("reports/form/partials/single_form.html", {
        "context_case_id": case_id,
        "instance": form,
        "form_meta": options.get('form_meta', {}),
        "maps_api_key": settings.GMAPS_API_KEY,
        "is_archived": form.doc_type == "XFormArchived",
        "domain": domain,
        'question_list_not_found': question_list_not_found,
        "form_data": form_data,
        "cases": cases,
        "form_table_options": {
            # todo: wells if display config has more than one column
            "put_loners_in_wells": False
        },
        "form_meta_data": form_meta_data,
        "auth_context": auth_context,
        "auth_user_info": auth_user_info,
        "user_info": user_info,
        "side_pane": side_pane,
        "user": user,
        "edit_session_data": edit_session_data,
        "show_edit_submission": show_edit_submission,
        "show_resave": show_resave,
    })
