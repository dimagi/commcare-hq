from django.contrib import admin
from dimagi.utils.django.management import export_as_csv_action
from .models import MALTRow


class MALTRowAdmin(admin.ModelAdmin):
    model = MALTRow
    list_display = ['domain_name', 'month']
    actions = [export_as_csv_action("Export selected rows as CSV", exclude=["id"])]


admin.site.register(MALTRow, MALTRowAdmin)
