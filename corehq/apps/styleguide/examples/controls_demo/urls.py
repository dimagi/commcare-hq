from __future__ import absolute_import
from django.conf.urls import url
from corehq.apps.styleguide.examples.controls_demo.views import *
from corehq.apps.styleguide.views.docs import (
    SelectControlFormExampleView,
    SelectControlViewExampleView,
)

urlpatterns = [
    url(r'^$', DefaultControlsDemoFormsView.as_view(),
        name=DefaultControlsDemoFormsView.urlname),
    url(r'^select_example/$', SelectControlDemoView.as_view(),
        name=SelectControlDemoView.urlname),

    # These URLs are for documentation purposes
    url(r'^forms/$', SelectControlFormExampleView.as_view(),
        name=SelectControlFormExampleView.urlname),
    url(r'^views/$', SelectControlViewExampleView.as_view(),
        name=SelectControlViewExampleView.urlname),
]
