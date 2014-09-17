from django.conf.urls import *
from corehq.apps.styleguide.views import *


urlpatterns = patterns('corehq.apps.styleguide.views',
    url(r'^$', MainStyleGuideView.as_view(), name=MainStyleGuideView.urlname),
    url(r'^forms/$', FormsStyleGuideView.as_view(), name=FormsStyleGuideView.urlname),
)
