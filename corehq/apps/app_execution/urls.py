from django.urls import path

from . import views

app_name = "app_execution"

urlpatterns = [
    path('', views.workflow_list, name="workflow_list"),
    path('new/', views.new_workflow, name="new_workflow"),
    path('<int:pk>/edit/', views.edit_workflow, name="edit_workflow"),
    path('<int:pk>/run/', views.run_workflow, name="run_workflow"),
    path('<int:pk>/logs/', views.workflow_log_list, name="workflow_logs"),
    path('<int:pk>/json_logs/', views.workflow_logs_json, name="logs_json"),
    path('<int:pk>/delete/', views.delete_workflow, name="delete_workflow"),
    path('log/<int:pk>', views.workflow_log, name="workflow_log"),
]
