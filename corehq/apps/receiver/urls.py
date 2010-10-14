from django.conf.urls.defaults import patterns

urlpatterns = patterns('corehq.apps.receiver.views',
    (r'$',  'post'),

)