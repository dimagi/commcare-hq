from corehq.apps.users.views import UploadCommCareUsers
from django.conf.urls.defaults import *

urlpatterns = patterns('corehq.apps.orgs.views',
    url(r'^base/$', 'orgs_base', name='orgs_base'),
    url(r'^(?P<org>[\w\.-]+)/$', 'orgs_landing', name='orgs_landing')
    )