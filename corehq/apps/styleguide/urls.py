from django.conf.urls import include, re_path as url

from corehq.apps.styleguide.views import (
    AtomsStyleGuideView,
    MainStyleGuideView,
    MoleculesStyleGuideView,
    OrganismsStyleGuideView,
    PagesStyleGuideView,
)
from corehq.apps.styleguide.views.docs import default

from corehq.apps.styleguide.views import bootstrap5

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
    url(r'^b5/$', bootstrap5.styleguide_home, name="styleguide_home_b5"),
    url(r'^b5/atoms/accessibility/$', bootstrap5.styleguide_atoms_accessibility,
        name="styleguide_atoms_accessibility_b5"),
    url(r'^b5/atoms/typography/$', bootstrap5.styleguide_atoms_typography,
        name="styleguide_atoms_typography_b5"),
    url(r'^b5/atoms/colors/$', bootstrap5.styleguide_atoms_colors,
        name="styleguide_atoms_colors_b5"),
]
