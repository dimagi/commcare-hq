from django.conf.urls.defaults import *
from .dispatcher import HQAnnouncementAdminInterfaceDispatcher
from .views import AnnouncementAdminCRUDFormView, TemplatedEmailer

urlpatterns = patterns('corehq.apps.announcements.views',
    url(r'^$', 'default_announcement', name="default_announcement_admin"),
    url(r'^email/$', TemplatedEmailer.as_view(), name="announcement_email"),
    url(r'^clear/((?P<announcement_id>[\w_]+)/)$', 'clear_announcement', name="clear_announcement"),
    url(r'^form/(?P<form_type>[\w_]+)/(?P<action>[(update)|(new)|(delete)]+)/((?P<item_id>[\w_]+)/)?$',
        AnnouncementAdminCRUDFormView.as_view(), name="announcement_item_form"),
    HQAnnouncementAdminInterfaceDispatcher.url_pattern(),
)
