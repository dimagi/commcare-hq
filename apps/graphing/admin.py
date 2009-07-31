from django.contrib import admin
from django.contrib.contenttypes import generic
from graphing.models import *

class RawGraphAdmin(admin.ModelAdmin):
    list_display = ('id','shortname','title','data_source','table_name','display_type')
    list_filter = ['data_source','table_name','display_type',]
    
class BaseGraphAdmin(admin.ModelAdmin):
    list_display = ('id','shortname','title')
    list_filter = []        

class GraphGroupAdmin(admin.ModelAdmin):
    list_display= ('id','name','description','num_graphs','parent_group')
    list_filter = ['parent_group']

class GraphPrefAdmin(admin.ModelAdmin):
    list_display=('id','user','num_groups')
    list_filter=['user']

admin.site.register(RawGraph,RawGraphAdmin)
admin.site.register(BaseGraph,BaseGraphAdmin)
admin.site.register(GraphGroup,GraphGroupAdmin)
admin.site.register(GraphPref, GraphPrefAdmin)
