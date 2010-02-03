from django.contrib.auth.decorators import login_required
from django.http import HttpResponse

#from django.core.files.base import ContentFile

from rapidsms.webui.utils import render_to_response

from photos.models import Photo
'''
    This isn't really supposed to work as a test right now, it's more to describe how to use the system

    >>> p = Photo(name="test image", original_image="apps/photos/tests/test.jpg")
    >>> p.save()
    >>> n = p.name
    >>> i = Photo.objects.get(name=n)
    >>> i.display.url
    u'/data/photos/test_display.jpg'
    >>> from django.test.client import Client
    >>> c = Client()
    >>> resp = c.get('/data/photos/test_display.jpg')
    >>> resp.status_code
    200
    >>> resp = c.get('/photo/%s' % i.id)
    >>> resp.status_code
    200
'''

@login_required()
def recent(request, template_name="photos/list.html"):  # default page
    photos = Photo.objects.all()
    return render_to_response(request, template_name, {'photos' : photos})
    
def show(request, photo_id, template_name="photos/single.html"):
    p = Photo.objects.get(id=photo_id)
    return render_to_response(request, template_name, {'photo' : p})