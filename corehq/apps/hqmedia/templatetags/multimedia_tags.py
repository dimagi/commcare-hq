import uuid
from django import template
import json
from corehq.apps.app_manager.templatetags.xforms_extras import trans
from corehq.apps.hqwebapp.templatetags.hq_shared_tags import static

register = template.Library()

@register.simple_tag
def render_multimedia_map(filename, type, content):

    type = type[0].capitalize() + type[1:].lower()
    template = """<tr id="%(item_id)s">
    <td class="hqmedia-status" style="vertical-align:middle; text-align:center;">%(status)s</td>
    <td class="hqmedia-action" style="vertical-align:middle; text-align:center;">%(action)s</td>
    <td class="hqmedia-preview" style="vertical-align:middle; text-align:center;">%(preview)s</td>
    <td class="hqmedia-path" style="vertical-align:middle;">%(path)s</td>
</tr>"""
    action_word = "Open"
    if type == "Image":
        action_word = "Preview"
    elif type == "Audio":
        action_word = "Play"

    if content:
        status = '<span class="label label-success"><i class="icon icon-white icon-ok"></i> Found</span>'
        action = '<a href="#" class="btn btn-primary">Replace %s</a>' % type
        preview = '<a href="%s" target="_blank" class="btn btn-info">%s %s</a>' % (content['url'], action_word, type)
        item_id = "hqmedia_%s_%s" % (type, content['m_id'])
    else:
        status = '<span class="label label-important"><i class="icon icon-white icon-remove"></i> Missing</span>'
        action = '<a href="#" class="btn btn-success">Upload %s</a>' % type
        preview = '<a href="#" target="_blank" class="btn btn-info hide">%s %s</a>' % (action_word, type)
        item_id = "hqmedia_%s_%s" % (type, uuid.uuid4())

    return template % {
        "item_id": item_id,
        "status": status,
        "action": action,
        "preview": preview,
        "path": filename
    }

@register.simple_tag
def render_ko_multimedia_map(filename, type, content):
    type = type[0].capitalize() + type[1:].lower()
    template = """<tr id="%(item_id)s">
        <td class="hqmedia-status" style="vertical-align:middle; text-align:center;">%(status)s</td>
        <td class="hqmedia-action" style="vertical-align:middle; text-align:center;">%(action)s</td>
        <td class="hqmedia-preview" style="vertical-align:middle; text-align:center;">%(preview)s</td>
        <td class="hqmedia-path" style="vertical-align:middle;">%(path)s</td>
    </tr>"""
    action_word = "Open"
    if type == "Image":
        action_word = "Preview"
    elif type == "Audio":
        action_word = "Play"

    if content:
        status = '<span class="label label-success"><i class="icon icon-white icon-ok"></i> Found</span>'
        action = '<a href="#" class="btn btn-primary">Replace %s</a>' % type
        preview = '<a href="%s" target="_blank" class="btn btn-info">%s %s</a>' % (content['url'], action_word, type)
        item_id = "hqmedia_%s_%s" % (type, content['m_id'])
    else:
        status = '<span class="label label-important"><i class="icon icon-white icon-remove"></i> Missing</span>'
        action = '<a href="#" class="btn btn-success">Upload %s</a>' % type
        preview = '<a href="#" target="_blank" class="btn btn-info hide">%s %s</a>' % (action_word, type)
        item_id = "hqmedia_%s_%s" % (type, uuid.uuid4())

    return template % {
        "item_id": item_id,
        "status": status,
        "action": action,
        "preview": preview,
        "path": filename
    }

@register.simple_tag
def missing_refs(number, type):
    template = "%(number)s %(type)s Reference%(gram)s missing"

    if number == 1:
        gram = " is"
    else:
        gram = "s are"

    return template % {"number": number,
                       "type": type,
                       "gram": gram}