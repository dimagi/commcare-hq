from django.urls import re_path as url

from custom.ucla.views import task_creation

urlpatterns = [
    url(r'ucla-task-creation/(?P<app_id>[\w-]+)/modules-(?P<module_id>[\w-]+)/forms-(?P<form_id>[\w-]+)/$',
        task_creation, name='ucla_task_creation')
]
