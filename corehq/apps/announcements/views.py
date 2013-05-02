from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect, HttpResponse
from corehq.apps.announcements.models import HQAnnouncement
from corehq.apps.crud.views import BaseAdminCRUDFormView
from corehq.apps.domain.decorators import require_superuser

@require_superuser
def default_announcement(request):
    from corehq.apps.announcements.interface import ManageGlobalHQAnnouncementsInterface
    return HttpResponseRedirect(ManageGlobalHQAnnouncementsInterface.get_url())

class AnnouncementAdminCRUDFormView(BaseAdminCRUDFormView):
    base_loc = "corehq.apps.announcements.forms"

@login_required()
def clear_announcement(request, announcement_id):
    if request.couch_user:
        try:
            announcement = HQAnnouncement.get(announcement_id)
            request.couch_user.announcements_seen.append(announcement._id)
            request.couch_user.save()
            return HttpResponse("cleared")
        except Exception as e:
            HttpResponse("Problem clearing announcement: %s" % e)
    return HttpResponse("not cleared")
