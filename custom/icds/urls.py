from django.conf.urls import patterns, url

urlpatterns = patterns('custom.icds.views',
    url(r'^tableau/$', 'tableau'),
)
