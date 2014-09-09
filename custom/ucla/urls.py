from django.conf.urls import patterns, url

urlpatterns = patterns('custom.ucla.views',
    url(r'ucla-task-creation/(?P<app_id>[\w-]+)/modules-(?P<module_id>[\w-]+)/forms-(?P<form_id>[\w-]+)/$',
        'task_creation', name='ucla_task_creation')
)
