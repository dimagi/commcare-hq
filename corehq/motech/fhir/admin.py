import json

from django.contrib import admin

from corehq.motech.fhir.models import (
    FHIRImportConfig,
    FHIRImportResourceProperty,
    FHIRImportResourceType,
    FHIRResourceProperty,
    FHIRResourceType,
    ResourceTypeRelationship,
)


class FHIRResourcePropertyInline(admin.TabularInline):
    model = FHIRResourceProperty
    verbose_name_plural = 'FHIR resource properties'
    fields = ('calculated_value_source', 'value_source_config',)
    readonly_fields = ('calculated_value_source',)

    def calculated_value_source(self, obj):
        if not (obj.case_property and obj.jsonpath):
            return ''

        value_source_config = {
            'case_property': obj.case_property.name,
            'jsonpath': obj.jsonpath,
        }
        if obj.value_map:
            value_source_config['value_map'] = obj.value_map

        return json.dumps(value_source_config, indent=2)


class FHIRResourceTypeAdmin(admin.ModelAdmin):
    model = FHIRResourceType
    list_display = (
        'domain',
        'name',
        'case_type',
    )
    list_display_links = (
        'domain',
        'name',
        'case_type',
    )
    list_filter = ('domain',)

    # Allows for creating resource properties without having to deal
    # with domains.
    inlines = [FHIRResourcePropertyInline]

    def has_add_permission(self, request):
        # Domains are difficult to manage with this interface. Create
        # using the Data Dictionary, and edit in Admin.
        return False


class FHIRImportConfigAdmin(admin.ModelAdmin):
    list_display = (
        'domain',
        'connection_settings',
        'frequency',
    )
    list_display_links = (
        'domain',
        'connection_settings',
        'frequency',
    )
    list_filter = ('domain',)
    list_select_related = ('connection_settings',)


class FHIRImportResourcePropertyInline(admin.TabularInline):
    model = FHIRImportResourceProperty
    verbose_name_plural = 'FHIR Importer resource properties'
    fields = ('value_source_config',)


class FHIRImportResourceTypeAdmin(admin.ModelAdmin):
    model = FHIRImportResourceType
    list_display = (
        'domain',
        'name',
        'case_type',
    )
    list_display_links = (
        'domain',
        'name',
        'case_type',
    )
    list_filter = ('import_config__domain',)
    list_select_related = ('import_config',)
    inlines = [FHIRImportResourcePropertyInline]

    def domain(self, obj):
        return obj.import_config.domain


class ResourceTypeRelationshipAdmin(admin.ModelAdmin):
    model = ResourceTypeRelationship
    list_display = (
        'domain',
        'resource_type',
        'related_resource_type',
    )
    list_display_links = (
        'domain',
        'resource_type',
        'related_resource_type',
    )
    list_filter = ('resource_type__import_config__domain',)
    list_select_related = ('resource_type__import_config',)

    def domain(self, obj):
        return obj.resource_type.domain


admin.site.register(FHIRResourceType, FHIRResourceTypeAdmin)
admin.site.register(FHIRImportConfig, FHIRImportConfigAdmin)
admin.site.register(FHIRImportResourceType, FHIRImportResourceTypeAdmin)
admin.site.register(ResourceTypeRelationship, ResourceTypeRelationshipAdmin)
