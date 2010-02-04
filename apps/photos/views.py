from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.http import HttpResponseRedirect
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

# default page - show all thumbnails by date
@login_required()
def recent(request, template_name="photos/list.html"):
    photos = Photo.objects.all()
    return render_to_response(request, template_name, {'photos' : photos})

# show a single photo + comments
@login_required()    
def show(request, photo_id, template_name="photos/single.html"):
    p = Photo.objects.get(id=photo_id)
    return render_to_response(request, template_name, {'photo' : p})
    
@login_required()
def populate(request):
    for i in (1,2,3):
        p = Photo(name="test image #%s" % i, original_image="apps/photos/tests/test%s.jpg" % i)
        p.save()
        
    return HttpResponseRedirect("/photos")
    
    