# process is here instead of views because in views it gets reloaded
# everytime someone hits a view and that messes up the process registration
# whereas models is loaded once
import sys
import logging
import traceback
from corehq.apps.receiver.models import Attachment
from django.db.models.signals import post_save

def process(sender, instance, created, **kwargs): #get sender, instance, created
    # only process newly created xforms, not all of them
    if not created:             return
    if not instance.is_xform(): return
    
    # yuck, this import is in here because they depend on each other
    from manager import XFormManager
    xml_file_name = instance.filepath
    logging.debug("PROCESS: Loading xml data from " + xml_file_name)
    
    # only run the xforms logic if the attachment isn't a duplicate 
    if not instance.is_duplicate():
        # TODO: make this a singleton?  Re-instantiating the manager every
        # time seems wasteful
        manager = XFormManager()
        try:
            manager.save_form_data(instance)
        except Exception, e:
            type, value, tb = sys.exc_info()
            traceback_string = '\n'.join(traceback.format_tb(tb))
            # we use 'xform_traceback' insetad of traceback since
            # dan's custom logger uses 'traceback'
            logging.error("Problem in xforms processing: " + str(e) + ". %s" % \
                          instance.display_string(),
                          extra={'file_name':xml_file_name, \
                                 'xform_traceback':traceback_string} )
            # print traceback_string
            
    else:
        pass
        
# Register to receive signals from corehq.apps.receiver
# print "connecting post save for attachments"
post_save.connect(process, sender=Attachment)

