from django import template
from django.core.urlresolvers import reverse

from receiver.models import Attachment

register = template.Library()


@register.simple_tag
def get_attachements_links(submission):
    ret = ''
    attachments = Attachment.objects.all().filter(submission=submission)
    for attach in attachments:        
        ret += ' <a href="%s">%d</a> |' % (reverse('receiver.views.single_attachment', kwargs={'attachment_id':attach.id}),attach.id)
    return ret[0:-1]