from django.contrib import admin
from backups.models import *

admin.site.register(BackupUser)
admin.site.register(Backup)

