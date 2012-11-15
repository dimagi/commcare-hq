from django.conf.urls.defaults import *
from corehq.apps.announcements.dispatcher import HQAnnouncementAdminInterfaceDispatcher
from corehq.apps.announcements.views import AnnouncementAdminCRUDFormView

urlpatterns = patterns('corehq.apps.announcements.views',
    url(r'^$', 'default_announcement', name="default_announcement_admin"),
    url(r'^form/(?P<form_type>[\w_]+)/(?P<action>[(update)|(new)|(delete)]+)/((?P<item_id>[\w_]+)/)?$',
        AnnouncementAdminCRUDFormView.as_view(), name="announcement_item_form"),
    HQAnnouncementAdminInterfaceDispatcher.url_pattern(),
)