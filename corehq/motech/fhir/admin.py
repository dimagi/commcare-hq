import json

from django.contrib import admin

from corehq.motech.fhir.models import (
    FHIRImporter,
    FHIRImporterResourceProperty,
    FHIRImporterResourceType,
    FHIRResourceProperty,
    FHIRResourceType,
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


class FHIRImporterAdmin(admin.ModelAdmin):
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


class FHIRImporterResourcePropertyInline(admin.TabularInline):
    model = FHIRImporterResourceProperty
    verbose_name_plural = 'FHIR Importer resource properties'
    fields = ('value_source_config',)


class FHIRImporterResourceTypeAdmin(admin.ModelAdmin):
    model = FHIRImporterResourceType
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
    list_filter = ('fhir_importer__domain',)
    list_select_related = ('fhir_importer',)
    inlines = [FHIRImporterResourcePropertyInline]

    def domain(self, obj):
        return obj.fhir_importer.domain


admin.site.register(FHIRResourceType, FHIRResourceTypeAdmin)
admin.site.register(FHIRImporter, FHIRImporterAdmin)
admin.site.register(FHIRImporterResourceType, FHIRImporterResourceTypeAdmin)
