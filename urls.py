from django.conf.urls.defaults import *
from django.conf import settings
import os

from corehq.util.modules import try_import

# Uncomment the next two lines to enable the admin:
from django.contrib import admin

admin.autodiscover()


from corehq.apps.hqwebapp.urls import domain_specific as hqwebapp_domain_specific
domain_specific = patterns('',
    (r'^apps/', include('corehq.apps.app_manager.urls')),
    (r'^receiver', include('corehq.apps.receiver.urls')),
    (r'^data/', include('corehq.apps.new_data.urls')),
    (r'^users/', include('corehq.apps.users.urls')),
    (r'^reports/', include('corehq.apps.reports.urls')),
    (r'^', include(hqwebapp_domain_specific))

)

urlpatterns = patterns('',
    # Uncomment the next line to enable the admin:
    (r'^admin/', include(admin.site.urls)),
    (r'^a/(?P<domain>\w+)/', include(domain_specific)),
    (r'^xep/', include('xep_hq_server.urls')),
    (r'', include('corehq.apps.hqwebapp.urls')),
    (r'', include('corehq.apps.domain.urls')),

)



# magic static media server (idea + implementation lifted from rapidsms)
for module_name in settings.INSTALLED_APPS:

    # leave django contrib apps alone. (many of them include urlpatterns
    # which shouldn't be auto-mapped.) this is a hack, but i like the
    # automatic per-app mapping enough to keep it. (for now.)
    if module_name.startswith("django."):
        continue

    # attempt to import this app's urls
    module = try_import("%s.urls" % (module_name))
    if not hasattr(module, "urlpatterns"): continue

    
    # if the MEDIA_URL does not contain a hostname (ie, it's just an
    # http path), and we are running in DEBUG mode, we will also serve
    # the media for this app via this development server. in production,
    # these files should be served directly
    if settings.DEBUG:
        if not settings.MEDIA_URL.startswith("http://"):
            media_prefix = settings.MEDIA_URL.strip("/")
            module_suffix = module_name.split(".")[-1]

            # does urls.py have a sibling "static" dir? (media is always
            # served from "static", regardless of what MEDIA_URL says)
            module_path = os.path.dirname(module.__file__)
            static_dir = "%s/static" % (module_path)
            if os.path.exists(static_dir):

                # map to {{ MEDIA_URL }}/appname
                urlpatterns += patterns("", url(
                    "^%s/%s/(?P<path>.*)$" % (
                        media_prefix,
                        module_suffix),
                    "django.views.static.serve",
                    {"document_root": static_dir}
                ))

