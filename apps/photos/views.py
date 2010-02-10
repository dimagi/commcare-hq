from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.http import HttpResponseRedirect
from rapidsms.webui.utils import render_to_response

from photos.models import Photo

import os
import settings

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
def import_photos(request):
    path = settings.RAPIDSMS_APPS['receiver']['attachments_path'] # -> data/attachments

    def is_img(filename):
        return (filename.endswith('.jpg') or filename.endswith('.jpeg') or filename.endswith('.png'))
    
    def not_in_db_already(filename):
        # Note that there's a query for each file here - another way would be to load all existing files to a list in one operation and work with that
        # but, that might generate huge list when there are a lot of photos in the DB, and might cause data freshness issues in some edge cases
        # so, we just do n queries each time (where n is probably not too big) instead
        return (Photo.objects.filter(original_image="%s/%s" % (path, filename)).count() == 0)
    
    files = os.listdir(path)
    img_files = filter(is_img, files)
    new_img_files = filter(not_in_db_already, img_files)
    
    for f in new_img_files:
        p = Photo(name=f, original_image="%s/%s" % (path, f))
        p.save()
    
    return HttpResponseRedirect("/photos")


    
    
@login_required()
def populate(request):
    for i in (1,2,3):
        p = Photo(name="test image #%s" % i, original_image="apps/photos/tests/test%s.jpg" % i)
        p.save()
        
    return HttpResponseRedirect("/photos")
    
    