from xformmanager.manager import *
from xformmanager.xformdef import *
import logging

def create_xsd_and_populate(xsd_file_name, xml_file_name=''):
    # Create a new form definition
    manager = XFormManager()
    
    f = open(os.path.join(os.path.dirname(__file__),xsd_file_name),"r")
    formdefmodel = manager.add_schema(xsd_file_name, f)
    f.close()
    
    populate(xml_file_name, manager)
    return formdefmodel

def populate(xml_file_name, manager=None):
    if xml_file_name is not None:
        # and input one xml instance
        #arguments: data_stream_pointer, formdef, formdefmodel_id, submission_id
        submission = create_fake_submission()
        if manager is None: manager = XFormManager()
        manager.save_form_data( os.path.join(os.path.dirname(__file__), xml_file_name) , submission )

from receiver.tests.submissions import *
def create_fake_submission():
    makeNewEntry('simple-meta.txt','simple-body.txt')
    attachment = Attachment.objects.latest('id')
    return attachment
    