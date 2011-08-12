from django.conf.urls.defaults import patterns, url

urlpatterns = patterns('corehq.apps.translations.views',
    url(r'^api/suggestions/$', 'get_translations'),
    url(r'^api/set/$', 'set_translations', name="set_translation"),
    url(r'^edit/$', 'edit'),
)
