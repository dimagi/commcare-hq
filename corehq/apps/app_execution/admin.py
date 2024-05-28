from django.contrib import admin

from .models import AppWorkflowConfig


@admin.register(AppWorkflowConfig)
class AppWorkflowAdmin(admin.ModelAdmin):
    list_display = ('domain', 'app_id', 'user_id', 'django_user')
