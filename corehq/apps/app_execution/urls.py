from django.urls import path

from . import views

app_name = "app_execution"

urlpatterns = [
    path('', views.workflow_list, name="workflow_list"),
    path('new/', views.new_workflow, name="new_workflow"),
    path('edit/<int:pk>', views.edit_workflow, name="edit_workflow"),
    path('test/<int:pk>', views.test_workflow, name="test_workflow"),
]
