from django.conf.urls import patterns, include

urlpatterns = patterns(
    '',
    (r'^99dots/', include("custom.enikshay.integrations.ninetyninedots.urls")),
)
