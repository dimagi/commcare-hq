from django import template
import json
from corehq.apps.app_manager.templatetags.xforms_extras import trans
from corehq.apps.hqwebapp.templatetags.hq_shared_tags import static

register = template.Library()

@register.simple_tag
def render_multimedia_map(filename, type, content):

    type = type[0].capitalize() + type[1:].lower()
    template = """<li class="%(type)sfile" data-form-path="%(filename)s" data-media-type="CommCare%(type)s"%(id)s>
<img src="%(indicator_image)s" alt="%(indicator_status)s" class="indicator" />
<a href="#" data-form-path="%(filename)s" class="upload_media"%(action_data)s>%(action)s</a>
%(filename)s
%(view_action)s
</li>"""
    if content:
        action_data = ' data-replace-file="true"'
        action = "Replace %s" % type
        indicator_image = static("hqmedia/img/checkmark.png")
        indicator_status = "included"
        view_action = '<a href="%s" class="view_media">Open %s</a>' % (content['url'], type)
        item_id = ' id="media_item_%s"' % content['m_id']
    else:
        action_data = ''
        action = "Upload %s" % type
        indicator_image = static("hqmedia/img/no_sign.png")
        indicator_status = "not included"
        view_action = ""
        item_id = ''

    return template % {"type": type, "indicator_image": indicator_image, "indicator_status": indicator_status,
                       "action_data": action_data, "action": action, "filename": filename,
                       "view_action": view_action, "id": item_id}