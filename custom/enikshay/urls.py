from django.conf.urls import include, url

urlpatterns = [
    url(r'^99dots/', include("custom.enikshay.integrations.ninetyninedots.urls")),
]
