from django.contrib import admin
from corehq.apps.domain.models import OldDomain, OldSettings
from corehq.apps.registration.models import OldRegistrationRequest

class DomainAdmin(admin.ModelAdmin):
    model = OldDomain

class RegistrationRequestAdmin(admin.ModelAdmin):
    model = OldRegistrationRequest
    
class SettingsAdmin(admin.ModelAdmin):
    model = OldSettings

admin.site.register(OldDomain, DomainAdmin)
admin.site.register(OldRegistrationRequest, RegistrationRequestAdmin)
admin.site.register(OldSettings, SettingsAdmin)
