from __future__ import absolute_import
from collections import OrderedDict
from functools import partial

from django.template.loader import render_to_string
from django.urls import reverse
from django import template
from django.utils.html import format_html
from couchdbkit.exceptions import ResourceNotFound
from corehq import privileges
from corehq.apps.cloudcare import CLOUDCARE_DEVICE_ID
from corehq.apps.hqwebapp.templatetags.hq_shared_tags import toggle_enabled

from corehq.apps.receiverwrapper.auth import AuthContext
from corehq.apps.hqwebapp.doc_info import get_doc_info_by_id, DocInfo
from corehq.apps.locations.permissions import can_edit_form_location
from corehq.apps.reports.formdetails.readable import get_readable_data_for_submission
from corehq import toggles
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.util.timezones.utils import get_timezone_for_request
from corehq.util.xml_utils import indent_xml
from casexml.apps.case.xform import extract_case_blocks
from casexml.apps.case import const
from casexml.apps.case.templatetags.case_tags import case_inline_display
from corehq.apps.hqwebapp.templatetags.proptable_tags import (
    get_tables_as_columns, get_default_definition)
from dimagi.utils.parsing import json_format_datetime
from django_prbac.utils import has_privilege
import six


register = template.Library()


@register.simple_tag
def render_form_xml(form):
    xml = form.get_xml()
    if isinstance(xml, six.text_type):
        xml = xml.encode('utf-8', errors='replace')
    formatted_xml = indent_xml(xml) if xml else ''
    return format_html(u'<pre class="prettyprint linenums"><code class="no-border language-xml">{}</code></pre>',
                       formatted_xml)


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
    case_id = options.get('case_id')
    side_pane = options.get('side_pane', False)
    user = options.get('user', None)
    request = options.get('request', None)
    support_enabled = toggle_enabled(request, toggles.SUPPORT)

    form_data, question_list_not_found = get_readable_data_for_submission(form)

    context = {
        "context_case_id": case_id,
        "instance": form,
        "is_archived": form.is_archived,
        "edit_info": _get_edit_info(form),
        "domain": domain,
        'question_list_not_found': question_list_not_found,
        "form_data": form_data,
        "form_table_options": {
            # todo: wells if display config has more than one column
            "put_loners_in_wells": False
        },
        "side_pane": side_pane,
    }

    context.update(_get_cases_changed_context(domain, form, case_id))
    context.update(_get_form_metadata_context(domain, form, support_enabled))
    context.update(_get_display_options(request, domain, user, form, support_enabled))
    context.update(_get_edit_info(form))
    return render_to_string("reports/form/partials/single_form.html", context, request=request)


def _get_edit_info(instance):
    info = {
        'was_edited': False,
        'is_edit': False,
    }
    if instance.is_deprecated:
        info.update({
            'was_edited': True,
            'latest_version': instance.orig_id,
        })
    if getattr(instance, 'edited_on', None) and getattr(instance, 'deprecated_form_id', None):
        info.update({
            'is_edit': True,
            'edited_on': instance.edited_on,
            'previous_version': instance.deprecated_form_id
        })
    return info


def _get_display_options(request, domain, user, form, support_enabled):
    user_can_edit = (
        request and user and request.domain and user.can_edit_data()
    )
    show_edit_options = (
        user_can_edit
        and can_edit_form_location(domain, user, form)
    )
    show_edit_submission = (
        user_can_edit
        and has_privilege(request, privileges.DATA_CLEANUP)
        and not form.is_deprecated
    )

    show_resave = (
        user_can_edit and support_enabled
    )

    return {
        "show_edit_options": show_edit_options,
        "show_edit_submission": show_edit_submission,
        "show_resave": show_resave,
    }


def _get_form_metadata_context(domain, form, support_enabled=False):
    meta = _top_level_tags(form).get('meta', None) or {}
    meta['received_on'] = json_format_datetime(form.received_on)
    meta['server_modified_on'] = json_format_datetime(form.server_modified_on) if form.server_modified_on else ''
    if support_enabled:
        meta['last_sync_token'] = form.last_sync_token

    definition = get_default_definition(sorted_form_metadata_keys(meta.keys()))
    form_meta_data = get_tables_as_columns(meta, definition, timezone=get_timezone_for_request())
    if getattr(form, 'auth_context', None):
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

    return {
        "form_meta_data": form_meta_data,
        "auth_context": auth_context,
        "auth_user_info": auth_user_info,
        "user_info": user_info,
    }


def _get_cases_changed_context(domain, form, case_id=None):
    case_blocks = extract_case_blocks(form)
    for i, block in enumerate(list(case_blocks)):
        if case_id and block.get(const.CASE_ATTR_ID) == case_id:
            case_blocks.pop(i)
            case_blocks.insert(0, block)
    cases = []
    for b in case_blocks:
        this_case_id = b.get(const.CASE_ATTR_ID)
        try:
            this_case = CaseAccessors(domain).get_case(this_case_id) if this_case_id else None
            valid_case = True
        except ResourceNotFound:
            this_case = None
            valid_case = False

        if this_case and this_case.case_id:
            url = reverse('case_details', args=[domain, this_case.case_id])
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
            "table": get_tables_as_columns(b, definition, timezone=get_timezone_for_request()),
            "url": url,
            "valid_case": valid_case,
            "case_type": this_case.type if valid_case else None,
        })

    return {
        'cases': cases
    }


def _top_level_tags(form):
        """
        Returns a OrderedDict of the top level tags found in the xml, in the
        order they are found.

        """
        to_return = OrderedDict()

        element = form.get_xml_element()
        if element is None:
            return OrderedDict(sorted(form.form_data.items()))

        for child in element:
            # fix {namespace}tag format forced by ElementTree in certain cases (eg, <reg> instead of <n0:reg>)
            key = child.tag.split('}')[1] if child.tag.startswith("{") else child.tag
            if key == "Meta":
                key = "meta"
            to_return[key] = form.get_data('form/' + key)
        return to_return
