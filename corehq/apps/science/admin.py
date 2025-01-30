from django.contrib import admin

from .models import ExperimentEnabler


@admin.register(ExperimentEnabler)
class ExperimentEnablerAdmin(admin.ModelAdmin):
    list_display = ('campaign', 'path', 'enabled_percent')
    ordering = ('campaign', 'path')
