import os

from django.conf import settings

# make our directories if they're not there
for dir in [settings.XFORMMANAGER_SCHEMA_PATH,
            settings.XFORMMANAGER_EXPORT_PATH]:
    if not os.path.isdir(dir):
        os.mkdir(dir)
