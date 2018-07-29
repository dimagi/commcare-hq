from __future__ import absolute_import
from __future__ import unicode_literals
from django.contrib import admin
from dimagi.utils.django.management import export_as_csv_action
from .models import MALTRow


class MALTRowAdmin(admin.ModelAdmin):
    model = MALTRow
    list_display = ['month', 'domain_name', 'username', 'num_of_forms', 'wam']
    list_filter = ['month', 'domain_name', 'num_of_forms', 'wam']
    actions = [export_as_csv_action("Export selected rows as CSV", exclude=["id"])]


admin.site.register(MALTRow, MALTRowAdmin)
