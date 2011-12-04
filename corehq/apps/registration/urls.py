from django.conf.urls.defaults import *

urlpatterns = patterns('corehq.apps.registration.views',
    url(r'^$', 'register_user', name='new_user_registration'),
    url(r'^domain/', 'register_domain', name="new_domain_registration")
)