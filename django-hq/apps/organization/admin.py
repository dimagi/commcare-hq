from django.contrib import admin
from organization.models import *

#class OrganizationTypeAdmin(admin.ModelAdmin):
#    list_display = ('id','name','description')
#    list_filter = []  
#    
#class OrganizationRoleAdmin(admin.ModelAdmin):
#    list_display = ('id','name','description')
#    list_filter = []      
    
class OrganizationUnitAdmin(admin.ModelAdmin):
    list_display = ('id','name','description','member_of')
    list_filter = ['member_of',]  
    
class OrganizationGroupAdmin(admin.ModelAdmin):
    list_display = ('id','name','description',)
    list_filter = []        

#admin.site.register(OrganizationType,OrganizationTypeAdmin)
#admin.site.register(OrganizationRole,OrganizationRoleAdmin)
admin.site.register(OrganizationUnit,OrganizationUnitAdmin)
admin.site.register(OrganizationGroup,OrganizationGroupAdmin)