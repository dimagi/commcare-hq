from django.contrib.auth.decorators import login_required
from django.http import HttpResponse

#from django.core.files.base import ContentFile

from rapidsms.webui.utils import render_to_response

from photos.models import Photo


# p = Photo(name="test-no_medroot", original_image="data/photos/hoover.jpg")
# p.save()

@login_required()
def recent(request, template_name="photos/list.html"):  # default page
    photos = Photo.objects.all()
    return render_to_response(request, template_name, {'photos' : photos})
    
def show(request, photo_id, template_name="photos/single.html"):
    p = Photo.objects.get(id=photo_id)
    return render_to_response(request, template_name, {'photo' : p})