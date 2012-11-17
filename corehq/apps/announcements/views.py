from django.http import HttpResponseRedirect
from corehq.apps.crud.views import BaseAdminCRUDFormView
from corehq.apps.domain.decorators import require_superuser

@require_superuser
def default_announcement(request):
    from corehq.apps.announcements.interface import ManageGlobalHQAnnouncementsInterface
    return HttpResponseRedirect(ManageGlobalHQAnnouncementsInterface.get_url())

class AnnouncementAdminCRUDFormView(BaseAdminCRUDFormView):
    base_loc = "corehq.apps.announcements.forms"