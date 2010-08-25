import os
import logging
from django.conf import settings

# make our directories if they're not there
for dir in [settings.XFORMS_SCHEMA_PATH,
            settings.XFORMS_EXPORT_PATH]:
    if not os.path.isdir(dir):
        try:
            os.mkdir(dir)   
        except Exception, e:
            logging.error("Unable to write xforms path: %s, %s" % (dir, e))
