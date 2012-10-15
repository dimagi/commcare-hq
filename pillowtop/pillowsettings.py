import logging

# import local settings if we find them
try:
    #try to see if there's an environmental variable set for local_settings
    from local_pillow import *
except ImportError, e:
    logging.error("Local settings not found, loading defaults: %s" % (e))

