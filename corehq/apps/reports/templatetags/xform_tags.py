from __future__ import absolute_import, unicode_literals

from django import template
from django.utils.html import format_html

from corehq.util.xml_utils import indent_xml
import six


register = template.Library()


@register.simple_tag
def render_form_xml(form):
    xml = form.get_xml()
    if isinstance(xml, six.text_type):
        xml = xml.encode('utf-8', errors='replace')
    formatted_xml = indent_xml(xml) if xml else ''
    return format_html('<pre class="prettyprint linenums"><code class="no-border language-xml">{}</code></pre>',
                       formatted_xml)
