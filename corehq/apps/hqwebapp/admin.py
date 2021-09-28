from django.contrib import admin

from corehq.apps.hqwebapp.models import HQOauthApplication


@admin.register(HQOauthApplication)
class HQOauthApplicationAdmin(admin.ModelAdmin):
    list_display = (
        "id", "application_id", "application_name", "application_user", "application_client_type",
        "application_authorization_grant_type"
    )

    def application_id(self, obj):
        return obj.application.id

    def application_name(self, obj):
        return obj.application.name

    def application_user(self, obj):
        return obj.application.user.id

    def application_client_type(self, obj):
        return obj.application.client_type

    def application_authorization_grant_type(self, obj):
        return obj.application.authorization_grant_type
