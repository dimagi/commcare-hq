from django import template

from django.core.urlresolvers import reverse

from receiver.models import *
from django.contrib.contenttypes.models import ContentType
from types import ListType,TupleType

from xformmanager.models import *
import xformmanager.adapter.querytools as qtools
from organization.models import *
import organization.utils as utils
from datetime import timedelta
import dbanalyzer.dbhelper as dbhelper

register = template.Library()

import time

@register.simple_tag
def get_attachements_links(submission):
    ret = ''
    attachments = Attachment.objects.all().filter(submission=submission)
    for attach in attachments:        
        ##retstring += '&gt;&gt;&gt; <a href="%s">' % (reverse('view_current_patient', kwargs= {'patient_id': patient.id}))
        
        ret += ' <a href="%s">%d</a> |' % (reverse('receiver.views.single_attachment', kwargs={'attachment_id':attach.id}),attach.id)
        #ret += ' <a href="%s">%d</a> |' % (attach.get_media_url(), attach.id)
    return ret[0:-1]