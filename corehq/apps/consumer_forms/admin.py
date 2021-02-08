from django.contrib import admin

from .models import ConsumerForm


@admin.register(ConsumerForm)
class AuthenticatedLinkAdmin(admin.ModelAdmin):
    list_display = ('slug', 'domain', )
    list_filter = ('domain',)
