from django.contrib import admin
from .models import StockState


class StockStateAdmin(admin.ModelAdmin):
    model = StockState
    list_display = [
        'section_id',
        'case_id',
        'product_id',
        'stock_on_hand',
        'daily_consumption',
        'last_modified_date'
    ]
    list_filter = [
        'section_id',
        'case_id',
        'product_id',
        'last_modified_date'
    ]

admin.site.register(StockState, StockStateAdmin)
