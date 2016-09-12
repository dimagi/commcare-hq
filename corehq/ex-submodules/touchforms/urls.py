from django.conf.urls import *
from django.conf import settings
# Uncomment the next two lines to enable the admin:
# from django.contrib import admin
# admin.autodiscover()

media_prefix = settings.STATIC_URL.strip("/")

urlpatterns = patterns('',
    # Example:
    (r'^', include('touchforms.formplayer.urls')),
    (r'^%s/formplayer/(?P<path>.*)$' % media_prefix, 'django.views.static.serve',
        {'document_root': settings.STATIC_DOC_ROOT}),
    (r'^%s/(?P<path>.*)$' % media_prefix, 'django.views.static.serve',
        {'document_root': settings.STATIC_DOC_ROOT}),

    # Uncomment the admin/doc line below and add 'django.contrib.admindocs' 
    # to INSTALLED_APPS to enable admin documentation:
    # (r'^admin/doc/', include('django.contrib.admindocs.urls')),

    # Uncomment the next line to enable the admin:
    # (r'^admin/', include(admin.site.urls)),
)
