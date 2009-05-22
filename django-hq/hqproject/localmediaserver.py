import cherrypy
import cgi
import tempfile
import os
import shutil
import sys
import time
from cherrypy import wsgiserver
import django.core.handlers.wsgi
import logging


#Daniel  Myung 12/30/2008
#This is a script that runs a cherrypy HTTP server that does two things.
#1:  from its configuration file, it'll serve all the Django static media
#2:  It'll use the crypto services to serve the encrypted images over http as well.

# for sake of convenience, all settings for port config will be pulled from
# the django settings file

__author__ = "Dan Myung"

    
class mediaHandler:
    """fileUpload cherrypy application"""
    @cherrypy.expose
    def index(self):
        return ""

# remove any limit on the request body size; cherrypy's default is 100MB
# (maybe we should just increase it ?)
cherrypy.server.max_request_body_size = 0

# increase server socket timeout to 60s; we are more tolerant of bad
# quality client-server connections (cherrypy's defult is 10s)
cherrypy.server.socket_timeout = 60

if __name__ == '__main__':
    # CherryPy always starts with app.root when trying to map request URIs
    # to objects, so we need to mount a request handler root. A request
    # to '/' will be mapped to HelloWorld().index().
    sys.path.append(os.path.join(os.getcwd(),'..'))
    sys.path.append(os.path.join(os.getcwd(),'..','..','apps'))
    sys.path.append(os.path.join(os.getcwd(),'..','..','libs'))
    sys.path.append(os.path.join(os.getcwd(),'..'))
    os.environ['DJANGO_SETTINGS_MODULE'] = 'cchq_main.settings'
    
    from cchq_main import settings
    #load up the configuration file
    #alter the port config to reflect that of the settings
    globalconf = {'server.socket_host':'0.0.0.0',
            'server.socket_port': 8090,
            'log.error_file':'mediaserver.error.log'}
    mediaconf = {'/media':{'tools.staticdir.on':True,
                      'tools.staticdir.dir':settings.MEDIA_ROOT,
                      'tools.staticdir.index':'index.html'}
                 #,'/media/admin-media':{'tools.staticdir.dir':os.path.join(settings.MEDIA_ROOT,'admin-media')}
                 }
    
    cherrypy.config.update(globalconf)
    cherrypy.tree.mount(mediaHandler(),'/',mediaconf)
        
    try:        
        
        logging.info("Starting media runtime...")
        cherrypy.engine.start()
        cherrypy.engine.block() #this allows for control-c shutdown        
    except KeyboardInterrupt:
        logging.info("Keyboard interrupt, shutting down mediaserver")
        cherrypy.engine.stop()
        logging.info("Mediaserver shutdown successful")
