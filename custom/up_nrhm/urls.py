from django.conf.urls import patterns, url

urlpatterns = patterns('custom.up_nrhm.views',
                       url(r'^asha_af_report/$', 'asha_af_report', name='asha_af_report'),)
