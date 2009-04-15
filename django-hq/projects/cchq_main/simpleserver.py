import wsgiserver

import logging
import os
import sys
import wsgi_cchq

if __name__ == '__main__':    
    
        
    server = wsgiserver.CherryPyWSGIServer(
        ('0.0.0.0', 8000),  # Use '127.0.0.1' to only bind to the localhost
        wsgi_cchq.application
    )            
    try: 
        print "Starting server..."       
        server.start()                                
    except KeyboardInterrupt:
        print "Server Shutdown..."        
        server.stop()
