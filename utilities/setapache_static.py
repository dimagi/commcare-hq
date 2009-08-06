#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4
import logging
import os, sys
 
from rapidsms.webui import settings
from django.conf.urls.defaults import *

def run():
    # iterate each of the active rapidsms apps (from the ini),
    # and (attempt to) import the urls.py from each. it's okay
    # if this fails, since not all apps have a webui
    for rs_app in settings.RAPIDSMS_APPS.values():
        try:        
            # import the single "urlpatterns" attribute
            package_name = "%s.urls" % (rs_app["type"])
            module = __import__(package_name, {}, {}, ["urlpatterns"])
            
            mod_dir = os.path.dirname(os.path.abspath(module.__file__))
            static_dir = "%s/static" % mod_dir
            
    
            if not os.path.exists(os.path.join(settings.MEDIA_ROOT, rs_app["type"])):
                print "Setting static/ symlink for app: " + rs_app['type']
                if os.path.exists(static_dir):                    
                    print '\tsymlink set'
                    os.symlink(static_dir, os.path.join(settings.MEDIA_ROOT,rs_app["type"]))
                else:
                    print '\tno static directory, skipping.'
                    
            
        except Exception, e:
            logging.debug("No urlpatterns, let's skip")
