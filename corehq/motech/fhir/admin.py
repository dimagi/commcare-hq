from django.contrib import admin

from corehq.motech.fhir.models import FHIRResourceType, FHIRResourceProperty


class FHIRResourceTypeAdmin(admin.ModelAdmin):
    model = FHIRResourceType
    list_display = (
        'name',
        'case_type',
        'domain',
    )
    list_filter = ('domain',)


class FHIRResourcePropertyAdmin(admin.ModelAdmin):
    model = FHIRResourceProperty
    list_display = [
        'resource_type',
        'case_property_name'
    ]
    list_filter = ('resource_type__domain',)


admin.site.register(FHIRResourceType, FHIRResourceTypeAdmin)
admin.site.register(FHIRResourceProperty, FHIRResourcePropertyAdmin)
