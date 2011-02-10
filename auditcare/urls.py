from django.conf.urls.defaults import *

urlpatterns = patterns('',
    url(r'^auditor/?$', 'auditcare.views.auditAll', name='auditAll'),
)
