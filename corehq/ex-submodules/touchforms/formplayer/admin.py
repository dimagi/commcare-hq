from django.contrib import admin
from touchforms.formplayer.models import XForm, EntrySession, Session


class XFormAdmin(admin.ModelAdmin):
    list_display = ('name', 'namespace','file')

class EntrySessionAdmin(admin.ModelAdmin):
    list_display = ('session_id', 'user', 'form','session_name', 'created_date', 'last_activity_date')
    list_filter = ('user', 'form','session_name', 'created_date', 'last_activity_date')

admin.site.register(XForm, XFormAdmin)
admin.site.register(EntrySession, EntrySessionAdmin)
admin.site.register(Session)