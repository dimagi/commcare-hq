from django.urls import path

from corehq.apps.object_testing import views

app_name = "object_test"

urlpatterns = [
    path("", views.ObjectTestListView.as_view(), name="list"),
    path("<int:id>/", views.ObjectTestEditView.as_view(), name="edit"),
]
