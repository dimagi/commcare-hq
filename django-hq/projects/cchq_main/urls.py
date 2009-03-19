from django.conf.urls.defaults import *
from django.conf.urls import *

# Uncomment the next two lines to enable the admin:
from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',
    # Example:
    # (r'^cchq_groups/', include('cchq_groups.foo.urls')),
    
    (r'^i18n/$', include('django.conf.urls.il8n')),
    #(r'^jsi18n/$', 'django.views.i18n.javascript_catalog', {}),
    (r'^formreceiver/', include('submitlogger.urls')),
    (r'^modelrelationship/', include('modelrelationship.urls')),
    (r'^xformmanager/', include('xformmanager.urls')),
    

    # Uncomment the admin/doc line below and add 'django.contrib.admindocs' 
    # to INSTALLED_APPS to enable admin documentation:
    (r'^admin/doc/', include('django.contrib.admindocs.urls')),

    # Uncomment the next line to enable the admin:
    (r'^admin/(.*)', admin.site.root),
)
