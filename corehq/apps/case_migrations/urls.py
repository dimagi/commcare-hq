
from django.conf.urls import url

from .views import MigrationView, migration_restore

urlpatterns = [
    url(r'^edit/$', MigrationView.as_view(), name=MigrationView.urlname),
    url(r'^restore/(?P<case_id>[\w\-]+)/$', migration_restore, name='migration_restore'),
]
