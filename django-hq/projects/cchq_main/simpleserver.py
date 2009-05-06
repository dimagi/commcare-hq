import wsgiserver

from wsgiref.simple_server import make_server






import logging
import os
import sys
import wsgi_cchq

if __name__ == '__main__':    
    if len(sys.argv) != 2 and (sys.argv[1] != 'cp' or sys.argv[1] != 'pywsgi'):
        print """\tUsage: 
            simpleserver [servermode]
                Where servermode = cp | pywsgi              
            """                    
        print sys.argv
        sys.exit(1)
    mode = sys.argv[1]
    
    
    print "Starting server..."
    if mode == 'cp':
        # Use '127.0.0.1' to only bind to the localhost
        cpserver = wsgiserver.CherryPyWSGIServer(('0.0.0.0', 8000),wsgi_cchq.application)
        try:           
            cpserver.start()                                        
        except KeyboardInterrupt:
            print "Server Shutdown..."        
            cpserver.stop()        
    elif mode == 'pywsgi':
        httpd = make_server('', 8000, wsgi_cchq.application)
        httpd.serve_forever()
    
    
        
