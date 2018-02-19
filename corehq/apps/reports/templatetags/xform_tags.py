from __future__ import absolute_import
from __future__ import unicode_literals
from collections import OrderedDict
from functools import partial

from datetime import datetime
from django.template.loader import render_to_string
from django.urls import reverse
from django import template
from django.utils.html import format_html
from couchdbkit.exceptions import ResourceNotFound
from django.utils.translation import ugettext_lazy

from corehq import privileges
from corehq.apps.cloudcare import CLOUDCARE_DEVICE_ID
from corehq.apps.hqwebapp.templatetags.hq_shared_tags import toggle_enabled

from corehq.apps.receiverwrapper.auth import AuthContext
from corehq.apps.hqwebapp.doc_info import get_doc_info_by_id, DocInfo
from corehq.apps.locations.permissions import can_edit_form_location
from corehq.apps.reports.formdetails.readable import get_readable_data_for_submission
from corehq import toggles
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.util.timezones.conversions import ServerTime
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

FORM_OPERATIONS = {
    'archive': ugettext_lazy('Archive'),
    'unarchive': ugettext_lazy('Un-Archive'),
    'edit': ugettext_lazy('Edit'),
    'uuid_data_fix': ugettext_lazy('Duplicate ID fix')
}


@register.simple_tag
def render_form_xml(form):
    xml = form.get_xml()
    if isinstance(xml, six.text_type):
        xml = xml.encode('utf-8', errors='replace')
    formatted_xml = indent_xml(xml) if xml else ''
    return format_html('<pre class="prettyprint linenums"><code class="no-border language-xml">{}</code></pre>',
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
