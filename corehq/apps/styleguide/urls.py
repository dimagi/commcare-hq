from django.conf.urls import *
from corehq.apps.styleguide.views import *

doc_urlpatterns = patterns('corehq.apps.styleguide.views.docs',
    url(r'^$', 'default', name='sg_examples_default'),
    url(r'^simple_crispy/',
        include('corehq.apps.styleguide.examples.simple_crispy_form.urls')),
    url(r'^controls_demo/',
        include('corehq.apps.styleguide.examples.controls_demo.urls')),
)

urlpatterns = patterns('corehq.apps.styleguide.views',
    url(r'^$', MainStyleGuideView.as_view(), name=MainStyleGuideView.urlname),
    url(r'^forms/$', FormsStyleGuideView.as_view(),
        name=FormsStyleGuideView.urlname),
    url(r'^icons/$', IconsStyleGuideView.as_view(),
        name=IconsStyleGuideView.urlname),
    url(r'^colors/$', ColorsStyleGuide.as_view(),
        name=ColorsStyleGuide.urlname),
    url(r'^views/$', ClassBasedViewStyleGuideView.as_view(),
        name=ClassBasedViewStyleGuideView.urlname),
    (r'^docs/', include(doc_urlpatterns)),
)


