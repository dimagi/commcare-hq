from django.contrib import admin
from organization.models import * 
from django.contrib.auth.models import Group, User

class DomainAdmin(admin.ModelAdmin):
    list_display = ('id','name','description')
    list_filter = []  


class OrganizationTypeAdmin(admin.ModelAdmin):
    list_display = ('id','name','description','domain')
    list_filter = []  

class ExtUserAdmin(admin.ModelAdmin):
    list_display = ('id','username','primary_phone','email','domain')
    list_filter = ['domain']
    
class OrganizationAdmin(admin.ModelAdmin):
    fields = ('name','description','organization_type','domain','parent', 'members','supervisors')
    list_display = ('id','name','domain', 'parent', 'description',)
    list_filter = []  
    

class ReportScheduleAdmin(admin.ModelAdmin):
    list_display = ('id','active','name','description','report_class', 'report_frequency','report_delivery', 'recipient_user', 'organization', 'report_function')
    list_filter = ['active','report_class','report_frequency', 'report_delivery', 'recipient_user']
    
    


admin.site.register(OrganizationType,OrganizationTypeAdmin)
admin.site.register(ReportSchedule, ReportScheduleAdmin)
admin.site.register(ExtUser,ExtUserAdmin)

admin.site.register(Organization,OrganizationAdmin)
admin.site.register(Domain,DomainAdmin)
