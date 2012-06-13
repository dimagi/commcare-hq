from corehq.apps.users.views import UploadCommCareUsers
from django.conf.urls.defaults import *

urlpatterns = patterns('corehq.apps.orgs.views',
    url(r'^(?P<org>[\w\.-]+)/$', 'orgs_landing', name='orgs_landing'),
    url(r'^(?P<org>[\w\.-]+)/add_project/$', 'orgs_add_project', name='orgs_add_project'),
    url(r'^(?P<org>[\w\.-]+)/new_project/$', 'orgs_new_project', name='orgs_new_project'),
    url(r'^(?P<org>[\w\.-]+)/logo/$', 'orgs_logo', name='orgs_logo')
)