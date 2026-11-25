from django.contrib import admin

from .models import SidecarApp


@admin.register(SidecarApp)
class SidecarAppAdmin(admin.ModelAdmin):
    list_display = ['domain', 'name', 'slug', 'url', 'created_on', 'last_modified']
    search_fields = ['domain', 'name', 'slug', 'url']
