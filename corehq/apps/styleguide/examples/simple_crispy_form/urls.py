from django.urls import re_path as url

from corehq.apps.styleguide.examples.simple_crispy_form.views import (
    DefaultSimpleCrispyFormSectionView,
    SimpleCrispyFormView
)
from corehq.apps.styleguide.views.docs import (
    FormsSimpleCrispyFormExampleView,
    ViewsSimpleCrispyFormExampleView,
)

urlpatterns = [
    url(r'^$', DefaultSimpleCrispyFormSectionView.as_view(),
        name=DefaultSimpleCrispyFormSectionView.urlname),
    url(r'^example/$', SimpleCrispyFormView.as_view(),
        name=SimpleCrispyFormView.urlname),

    # These URLs are for documentation purposes
    url(r'^forms/$', FormsSimpleCrispyFormExampleView.as_view(),
        name=FormsSimpleCrispyFormExampleView.urlname),
    url(r'^views/$', ViewsSimpleCrispyFormExampleView.as_view(),
        name=ViewsSimpleCrispyFormExampleView.urlname),
]
