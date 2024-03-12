from django.conf.urls import re_path as url

from corehq.apps.styleguide.examples.bootstrap5.class_view import (
    ExampleCenteredPageView,
    ExampleChildSectionPageView,
    ExampleParentSectionPageView,
)
from corehq.apps.styleguide.examples.bootstrap5.functional_view import (
    simple_redirect_view,
    example_centered_page_view,
    example_section_page_view,
    example_parent_page_view,
)

urlpatterns = [
    url(r'^$', simple_redirect_view, name="example_views_b5"),
    url(r'^centered_page/$', ExampleCenteredPageView.as_view(),
        name=ExampleCenteredPageView.urlname),
    url(r'^centered_page_functional/$', example_centered_page_view,
        name="example_centered_page_functional_b5"),
    url(r'^example_section_functional/$', example_section_page_view,
        name="example_section_functional_b5"),
    url(r'^example_section/$', ExampleChildSectionPageView.as_view(),
        name=ExampleChildSectionPageView.urlname),
    url(r'^example_parent_functional/$', example_parent_page_view,
        name="example_parent_page_functional_b5"),
    url(r'^example_parent/$', ExampleParentSectionPageView.as_view(),
        name=ExampleParentSectionPageView.urlname),
]
