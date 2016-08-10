from django.conf.urls import patterns, include

urlpatterns = patterns(
    'custom.enikshay.integrations.ninetyninedots.views',
    (r'^99dots/', include("custom.enikshay.integrations.ninetyninedots.urls")),
)
