from django.contrib import admin
from submitlogger.models import *

class SubmitLogAdmin(admin.ModelAdmin):
    list_display = ('id','submit_time','submit_ip','bytes_received',)
    list_filter = ['submit_ip',]  
    
class AttachmentAdmin(admin.ModelAdmin):
    list_display = ('id','submission','filesize','filepath',)
    list_filter = ['submission',]    

admin.site.register(SubmitLog,SubmitLogAdmin)
admin.site.register(Attachment,AttachmentAdmin)