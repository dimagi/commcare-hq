from django.contrib import admin
from monitorregistry.models import *

class MonitorIdentityAdmin(admin.ModelAdmin):
    list_display = ('id','id_name','date_registered','active')
    list_filter = ['active','date_registered',]  
    
class MonitorDeviceAdmin(admin.ModelAdmin):
    list_display = ('id','phone','date_registered',)
    list_filter = ['identity','date_registered','active']    
    
class MonitorGroupAdmin(admin.ModelAdmin):
    list_display = ('id','name','description',)
    list_filter = []    

admin.site.register(MonitorIdentity,MonitorIdentityAdmin)
admin.site.register(MonitorDevice,MonitorDeviceAdmin)
admin.site.register(MonitorGroup,MonitorGroupAdmin)