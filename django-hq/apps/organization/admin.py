from django.contrib import admin
from organization.models import *

class OrganizationTypeAdmin(admin.ModelAdmin):
    list_display = ('id','name','description')
    list_filter = []  

class ExtUserAdmin(admin.ModelAdmin):
    list_display = ('id','username','primary_phone','email')
    list_filter = []
    
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ('id','name','description','member_of')
    list_filter = ['member_of',]  
    
class ExtRoleAdmin(admin.ModelAdmin):
    list_display = ('id','name','description',)
    list_filter = []      
    
#
#class OrgRelationshipTypeAdmin(admin.ModelAdmin):
#    list_display = ('name','description','directional')
#    list_filter = ['directional']      
#    
#class OrgRelationshipAdmin(admin.ModelAdmin):
#    list_display = ('parent_type','parent_id','relationship','child_type','child_id')
#    list_filter = ['relationship', 'parent_type','parent_id','child_type','child_id']      
#    


admin.site.register(OrganizationType,OrganizationTypeAdmin)

admin.site.register(ExtRole,ExtRoleAdmin)
admin.site.register(ExtUser,ExtUserAdmin)

admin.site.register(Organization,OrganizationAdmin)

