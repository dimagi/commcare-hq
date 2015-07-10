from django.contrib import admin
from .models import MALTRow


class MALTRowAdmin(admin.ModelAdmin):
    model = MALTRow
    list_display = ['domain_name', 'month']


admin.site.register(MALTRow, MALTRowAdmin)
