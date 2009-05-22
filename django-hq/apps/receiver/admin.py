from django.contrib import admin
from receiver.models import *

class SubmissionAdmin(admin.ModelAdmin):
    list_display = ('id','submit_time','submit_ip','bytes_received',)
    list_filter = ['submit_ip','domain']  
    
class AttachmentAdmin(admin.ModelAdmin):
    list_display = ('id','submission','filesize','attachment_content_type')
    list_filter = ['attachment_content_type',]    
    
class BackupAdmin(admin.ModelAdmin):
    list_display = ('id','submission','password','backup_code',)
    list_filter = []

admin.site.register(Submission,SubmissionAdmin)
admin.site.register(Attachment,AttachmentAdmin)
admin.site.register(Backup,BackupAdmin)