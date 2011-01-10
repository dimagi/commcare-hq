from django.contrib import admin
from corehq.apps.domain.models import Domain, RegistrationRequest, Settings

class DomainAdmin(admin.ModelAdmin):
    model = Domain

class RegistrationRequestAdmin(admin.ModelAdmin):
    model = RegistrationRequest
    
class SettingsAdmin(admin.ModelAdmin):
    model = Settings

admin.site.register(Domain, DomainAdmin)    
admin.site.register(RegistrationRequest, RegistrationRequestAdmin)
admin.site.register(Settings, SettingsAdmin)
