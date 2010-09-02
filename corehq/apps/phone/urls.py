from django.conf.urls.defaults import *

urlpatterns = patterns('',                     
    url(r'^backups/(?P<backup_id>\d+)/?$', 'corehq.apps.phone.views.restore', name='restore'),
    url(r'^phones/?$', 'corehq.apps.phone.views.index', name='phone_index'),
    url(r'^phones/(?P<phone_id>\d+)/?$', 'corehq.apps.phone.views.single_phone', name='single_phone'),
    url(r'^phones/phone_users/(?P<user_id>\d+)/?$', 'corehq.apps.phone.views.single_user', name='single_user'),
    url(r'^phones/phone_users/(?P<user_id>\d+)/new_user/?$', 'corehq.apps.phone.views.create_user', name='create_user'),
    url(r'^phones/phone_users/(?P<user_id>\d+)/link_user/?$', 'corehq.apps.phone.views.link_user', name='link_user'),
    url(r'^phones/phone_users/(?P<user_id>\d+)/delete_user/?$', 'corehq.apps.phone.views.delete_user', name='delete_user'),
    url(r'^phones/users/(?P<user_id>\d+)/?$', 'corehq.apps.phone.views.single_django_user', name='single_django_user'),
)
