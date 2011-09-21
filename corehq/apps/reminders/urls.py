from django.conf.urls.defaults import *

urlpatterns = patterns('corehq.apps.reminders.views',
    url(r'^$', 'default', name='reminders_default'),
    url(r'^all/$', 'list_reminders', name='list_reminders'),
    url(r'^add/$', 'add_reminder', name='add_reminder'),
    url(r'^edit/(?P<handler_id>[\w-]+)/$', 'add_reminder', name='edit_reminder'),
    url(r'^delete/(?P<handler_id>[\w-]+)/$', 'delete_reminder', name='delete_reminder'),
    url(r'^scheduled/', 'scheduled_reminders', name='scheduled_reminders'),
)