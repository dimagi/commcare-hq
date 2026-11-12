from django.urls import path

from corehq.apps.project_db.views import QueryProjectDBView

urlpatterns = [
    path('query/', QueryProjectDBView.as_view(), name=QueryProjectDBView.urlname),
]
