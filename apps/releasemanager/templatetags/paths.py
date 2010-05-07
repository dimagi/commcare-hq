import settings
import os

from django import template
from django.http import HttpRequest
from django.template import RequestContext
from django.core.urlresolvers import reverse


register = template.Library()

FILE_PATH = settings.RAPIDSMS_APPS['releasemanager']['file_path']

@register.simple_tag
def download_url(path):
    ''' returns a download URL for file path '''
    path = path.replace(FILE_PATH, '')[1:] # remove path + first slash
    url = reverse('download_link', kwargs={'path' : path})
    return url
    
    
@register.simple_tag
def filename(path):
    return os.path.basename(path)