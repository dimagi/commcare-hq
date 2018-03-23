from __future__ import absolute_import
from __future__ import unicode_literals
from django.contrib import admin
from .models import *


class StockReportAdmin(admin.ModelAdmin):
    model = StockReport
    list_display = ['date', 'type', 'form_id']
    list_filter = ['date', 'type']
    search_fields = ['form_id']


class StockTransactionAdmin(admin.ModelAdmin):
    model = StockTransaction
    list_display = ['report_date', 'section_id', 'type', 'subtype', 'case_id', 'product_id', 'quantity', 'stock_on_hand']
    list_filter = ['report__date', 'section_id', 'type', 'subtype']
    search_fields = ['case_id', 'product_id']

    def report_date(self, obj):
        return obj.report.date
    report_date.admin_order_field = 'report__date'

admin.site.register(StockReport, StockReportAdmin)
admin.site.register(StockTransaction, StockTransactionAdmin)
