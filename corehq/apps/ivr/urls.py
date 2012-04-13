from django.conf.urls.defaults import *

urlpatterns = patterns("corehq.apps.ivr.views",
    url(r"^tropo/$", "tropo", name="tropo"),
)

