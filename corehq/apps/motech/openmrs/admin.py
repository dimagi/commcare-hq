from django.contrib import admin
from corehq.apps.motech.openmrs.concepts.models import OpenmrsConcept


class OpenmrsConceptAdmin(admin.ModelAdmin):
    pass


admin.site.register(OpenmrsConcept, OpenmrsConceptAdmin)
