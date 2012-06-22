from django.db import models

# Create your models here.


#dmyung 6/21/2012
#this signal_emits has a scrub_meta method in it which is redundant with corehq.receiverwrapper.signals
#Once the receiver wrapper redundancy is removed, then this should be called explicitly
#from signal_emits import *

