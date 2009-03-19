from django.contrib import admin
from submitlogger.models import *

class SubmitLogAdmin(admin.ModelAdmin):
    list_display = ('id','submit_time','submit_ip','bytes_received',)
    list_filter = ['submit_ip',]    

admin.site.register(SubmitLog,SubmitLogAdmin)