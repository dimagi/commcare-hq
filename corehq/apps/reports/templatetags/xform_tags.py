from functools import partial

from django.template import RequestContext
from django.template.loader import render_to_string
from django.core.urlresolvers import reverse
from django import template
import pytz
from django.utils.html import escape
from django.utils.translation import ugettext as _
from couchdbkit.exceptions import ResourceNotFound
from corehq import privileges
from corehq.apps.cloudcare import CLOUDCARE_DEVICE_ID
from corehq.apps.hqwebapp.templatetags.hq_shared_tags import toggle_enabled

from corehq.apps.receiverwrapper.auth import AuthContext
from corehq.apps.hqwebapp.doc_info import get_doc_info_by_id, DocInfo
from corehq.apps.locations.permissions import can_edit_form_location
from corehq.apps.reports.formdetails.readable import get_readable_data_for_submission
from corehq import toggles
from corehq.util.timezones.conversions import ServerTime
from corehq.util.timezones.utils import get_timezone_for_request
from corehq.util.xml_utils import indent_xml
from couchforms.models import XFormInstance
from casexml.apps.case.xform import extract_case_blocks
from casexml.apps.case import const
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.templatetags.case_tags import case_inline_display
from corehq.apps.hqwebapp.templatetags.proptable_tags import (
    get_tables_as_columns, get_default_definition)
from django_prbac.utils import has_privilege


register = template.Library()


@register.simple_tag
def render_form_xml(form):
    xml = form.get_xml()
    formatted_xml = indent_xml(xml) if xml else ''
    return '<pre class="fancy-code prettyprint linenums"><code class="language-xml">%s</code></pre>' \
           % escape(formatted_xml)



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

    timezone = get_timezone_for_request()
    case_id = options.get('case_id')
    side_pane = options.get('side_pane', False)
    user = options.get('user', None)
    request = options.get('request', None)
    support_enabled = toggle_enabled(request, toggles.SUPPORT)

    _get_tables_as_columns = partial(get_tables_as_columns, timezone=timezone)

    # Form Data tab
    form_data, question_list_not_found = get_readable_data_for_submission(form)

    # Case Changes tab
    case_blocks = extract_case_blocks(form)
    for i, block in enumerate(list(case_blocks)):
        if case_id and block.get(const.CASE_ATTR_ID) == case_id:
            case_blocks.pop(i)
            case_blocks.insert(0, block)

    cases = []
    for b in case_blocks:
        this_case_id = b.get(const.CASE_ATTR_ID)
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

        definition = get_default_definition(
            sorted_case_update_keys(b.keys()),
            assume_phonetimes=(not form.metadata or
                               (form.metadata.deviceID != CLOUDCARE_DEVICE_ID)),
        )
        cases.append({
            "is_current_case": case_id and this_case_id == case_id,
            "name": case_inline_display(this_case),
            "table": _get_tables_as_columns(b, definition),
            "url": url,
            "valid_case": valid_case
        })

    # Form Metadata tab
    meta = form.top_level_tags().get('meta', None) or {}
    if support_enabled:
        meta['last_sync_token'] = form.last_sync_token

    definition = get_default_definition(sorted_form_metadata_keys(meta.keys()))
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

    user_can_edit = (
        request and user and request.domain
        and (user.can_edit_data() or user.is_commcare_user())
    )
    show_edit_options = (
        user_can_edit
        and can_edit_form_location(domain, user, form)
    )
    show_edit_submission = (
        user_can_edit
        and has_privilege(request, privileges.DATA_CLEANUP)
        and form.doc_type != 'XFormDeprecated'
    )

    show_resave = (
        user_can_edit and support_enabled
    )
    def _get_edit_info(instance):
        info = {
            'was_edited': False,
            'is_edit': False,
        }
        if instance.doc_type == "XFormDeprecated":
            info.update({
                'was_edited': True,
                'latest_version': instance.orig_id,
            })
        if getattr(instance, 'edited_on', None):
            info.update({
                'is_edit': True,
                'edited_on': instance.edited_on,
                'previous_version': instance.deprecated_form_id
            })
        return info

    return render_to_string("reports/form/partials/single_form.html", {
        "context_case_id": case_id,
        "instance": form,
        "is_archived": form.doc_type == "XFormArchived",
        "edit_info": _get_edit_info(form),
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
        "show_edit_options": show_edit_options,
        "show_edit_submission": show_edit_submission,
        "show_resave": show_resave,
    }, RequestContext(request))
