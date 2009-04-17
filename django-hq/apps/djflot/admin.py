from django.contrib import admin
from django.contrib.contenttypes import generic
from djflot.models import *

class RawGraphAdmin(admin.ModelAdmin):
    list_display = ('shortname','title','data_source','table_name','display_type')
    list_filter = ['data_source','table_name','display_type',]
        

admin.site.register(RawGraph,RawGraphAdmin)
