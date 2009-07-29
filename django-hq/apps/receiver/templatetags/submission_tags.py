from django import template
from django.core.urlresolvers import reverse

from receiver.models import Attachment

register = template.Library()


@register.simple_tag
def get_attachments_links(submission):
    ret = ''
    # this shouldn't include the original xform, if that exists
    attachments = submission.attachments.all()
    xform = submission.xform
    for attach in attachments:
        if attach != xform:
            ret += ' <a href="%s">%d</a> |' % (reverse('receiver.views.single_attachment', kwargs={'attachment_id':attach.id}),attach.id)
    return ret[0:-1]