import wsgiserver
import django.core.handlers.wsgi
import hq_wsgi
import logging

if __name__ == '__main__':
    import hq_wsgi
    server = wsgiserver.CherryPyWSGIServer(
        ('0.0.0.0', 8000),  # Use '127.0.0.1' to only bind to the localhost
        hq_wsgi.application
    )    
        
    try:        
        server.start()                                
    except KeyboardInterrupt:        
        server.stop()
