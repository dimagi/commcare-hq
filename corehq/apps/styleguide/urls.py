from __future__ import absolute_import
from django.conf.urls import include, url

from corehq.apps.styleguide.views import (
    ClassBasedViewStyleGuideView,
    ColorsStyleGuide,
    CSSStyleGuideView,
    FormsStyleGuideView,
    IconsStyleGuideView,
    MainStyleGuideView,
)
from corehq.apps.styleguide.views.docs import default

doc_urlpatterns = [
    url(r'^$', default, name='sg_examples_default'),
    url(r'^simple_crispy/',
        include('corehq.apps.styleguide.examples.simple_crispy_form.urls')),
    url(r'^controls_demo/',
        include('corehq.apps.styleguide.examples.controls_demo.urls')),
]

urlpatterns = [
    url(r'^$', MainStyleGuideView.as_view(), name=MainStyleGuideView.urlname),
    url(r'^forms/$', FormsStyleGuideView.as_view(),
        name=FormsStyleGuideView.urlname),
    url(r'^icons/$', IconsStyleGuideView.as_view(),
        name=IconsStyleGuideView.urlname),
    url(r'^colors/$', ColorsStyleGuide.as_view(),
        name=ColorsStyleGuide.urlname),
    url(r'^css/$', CSSStyleGuideView.as_view(),
        name=CSSStyleGuideView.urlname),
    url(r'^views/$', ClassBasedViewStyleGuideView.as_view(),
        name=ClassBasedViewStyleGuideView.urlname),
    url(r'^docs/', include(doc_urlpatterns)),
]


