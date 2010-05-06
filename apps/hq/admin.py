from django.contrib import admin
from hq.models import * 
from django.contrib.auth.models import Group, User
from reporters.models import Reporter

class OrganizationTypeAdmin(admin.ModelAdmin):
    list_display = ('id','name','description','domain')
    list_filter = []  

class OrganizationAdmin(admin.ModelAdmin):
    fields = ('name','description','organization_type','domain','parent', 'members','supervisors')
    list_display = ('id','name','domain', 'parent', 'description',)
    list_filter = []  
    

class ReportScheduleAdmin(admin.ModelAdmin):
    list_display = ('id','active','name','description','report_class', 'report_frequency','report_delivery', 'recipient_user', 'organization', 'report_function')
    list_filter = ['active','report_class','report_frequency', 'report_delivery', 'recipient_user']

class ReporterProfileAdmin(admin.ModelAdmin):
    list_display = ('id','chw_id','report_identity','domain','organization','active','approved','reporter')
    list_filter = ['active','approved','domain', 'organization']
    


admin.site.register(OrganizationType,OrganizationTypeAdmin)
admin.site.register(ReportSchedule, ReportScheduleAdmin)

admin.site.register(Organization,OrganizationAdmin)
admin.site.register(ReporterProfile, ReporterProfileAdmin)
admin.site.register(BlacklistedUser)