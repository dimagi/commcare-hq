from django.conf.urls.defaults import patterns

urlpatterns = patterns('corehq.apps.new_data.views',
    ('^$', 'data'),
)