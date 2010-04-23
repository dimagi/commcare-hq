from django.contrib import admin
from xformmanager.models import *



class FormDefModelAdmin(admin.ModelAdmin):
    list_display = ('id','uploaded_by', 'domain', 'form_display_name','form_name', 'submit_time',)
    list_filter = ["domain"]

class MetaDataModelAdmin(admin.ModelAdmin):
    list_display = ( 'formname','formversion','deviceid','timestart','timeend','username','chw_id','uid', 'attachment', 'raw_data', 'formdefmodel')
    list_filter = ( 'formname','formversion','deviceid','timestart','timeend','username','chw_id','formdefmodel')

admin.site.register(FormDefModel,FormDefModelAdmin)
admin.site.register(ElementDefModel)
admin.site.register(Metadata, MetaDataModelAdmin)

admin.site.register(FormDataPointer)
admin.site.register(FormDataColumn)
admin.site.register(FormDataGroup)
