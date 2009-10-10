from django.contrib import admin
from models import *


class CaseFormIdInline(admin.TabularInline):
    model = CaseFormIdentifier
    extra = 5

class CaseAdmin(admin.ModelAdmin):
    inlines = [CaseFormIdInline]
    
admin.site.register(Case, CaseAdmin)
admin.site.register(CaseFormIdentifier)
admin.site.register(FormIdentifier)
admin.site.register(SqlReport)
admin.site.register(ColumnFormatter)
