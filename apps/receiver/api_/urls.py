from django.conf.urls.defaults import *
# this module is called api_ because importing from "api.resources" 
# conflicts with the builtin python namespace
from receiver.api_.resources import *

urlpatterns = patterns('',
   # Retrieve all forms submitted to a specific schema
   # ?format=xml&start-id=<start-id>&end-id=<end-id>
   (r'^api/submissions/$', get_submissions ),
   (r'^api/(?P<domain_id>\d+)/submissions/$', get_submissions ),    
)

