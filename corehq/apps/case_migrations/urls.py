from django.conf.urls import url

from .views import migration_restore

urlpatterns = [
    url(r'^restore/(?P<case_id>[\w\-]+)/$', migration_restore, name='migration_restore'),
]
