from django.contrib import admin

from ccorganization.models import *

class EdgeTypeAdmin(admin.ModelAdmin):
    list_display = ('name','description','directional')
    list_filter = ['directional']    
    pass


class EdgeAdmin(admin.ModelAdmin):
    list_display = ('parent_type','parent_id','relationship','child_type','child_id')
    list_filter = ['relationship', 'parent_type','parent_id','child_type','child_id']    

admin.site.register(EdgeType,EdgeTypeAdmin)
admin.site.register(Edge,EdgeAdmin)