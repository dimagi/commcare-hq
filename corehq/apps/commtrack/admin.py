from django.contrib import admin
from .models import StockState, SQLProduct


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
        'last_modified_date'
    ]
    search_fields = ['case_id', 'product_id']


class ProductAdmin(admin.ModelAdmin):
    model = SQLProduct

    list_display = [
        'domain',
        'name',
        'is_archived',
        'product_id'
    ]
    list_filter = [
        'domain',
        'is_archived',
    ]
    search_fields = [
        'name',
        'product_id'
    ]


admin.site.register(StockState, StockStateAdmin)
admin.site.register(SQLProduct, ProductAdmin)
