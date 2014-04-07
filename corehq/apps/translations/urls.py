from django.conf.urls import patterns, url

urlpatterns = patterns(
    'corehq.apps.translations.views',
    url(r'^api/suggestions/$', 'get_translations', name='get_translations'),
)
