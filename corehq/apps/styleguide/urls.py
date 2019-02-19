from __future__ import absolute_import
from __future__ import unicode_literals
from django.conf.urls import include, url

from corehq.apps.styleguide.views import (
    AtomsStyleGuideView,
    MainStyleGuideView,
    MoleculesStyleGuideView,
    OrganismsStyleGuideView,
    PagesStyleGuideView,
)
from corehq.apps.styleguide.views.docs import default

doc_urlpatterns = [
    url(r'^$', default, name='sg_examples_default'),
    url(r'^simple_crispy/',
        include('corehq.apps.styleguide.examples.simple_crispy_form.urls')),
]

urlpatterns = [
    url(r'^$', MainStyleGuideView.as_view(), name=MainStyleGuideView.urlname),
    url(r'^atoms/$', AtomsStyleGuideView.as_view(),
        name=AtomsStyleGuideView.urlname),
    url(r'^molecules/$', MoleculesStyleGuideView.as_view(),
        name=MoleculesStyleGuideView.urlname),
    url(r'^organisms/$', OrganismsStyleGuideView.as_view(),
        name=OrganismsStyleGuideView.urlname),
    url(r'^pages/$', PagesStyleGuideView.as_view(),
        name=PagesStyleGuideView.urlname),
    url(r'^docs/', include(doc_urlpatterns)),
]


