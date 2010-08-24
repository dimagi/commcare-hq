import os
import logging
from django.conf import settings

# make our directories if they're not there
for dir in [settings.XFORMMANAGER_SCHEMA_PATH,
            settings.XFORMMANAGER_EXPORT_PATH]:
    if not os.path.isdir(dir):
        try:
            os.mkdir(dir)   
        except Exception, e:
            logging.error("Unable to write xformmanager path: %s, %s" % (dir, e))
