from django.contrib import admin
from xformmanager.models import *



class FormDefModelAdmin(admin.ModelAdmin):
    list_display = ('id','uploaded_by', 'get_domain', 'form_display_name','form_name', 'submit_time',)
    list_filter = []

admin.site.register(FormDefModel,FormDefModelAdmin)
admin.site.register(ElementDefModel)
admin.site.register(Metadata)