from django.contrib import admin
from .models import StockReport


class StockReportAdmin(admin.ModelAdmin):
    model = StockReport
    list_display = ['date', 'type', 'form_id']
    list_filter = ['date', 'type']
    search_fields = ['form_id']


admin.site.register(StockReport, StockReportAdmin)
