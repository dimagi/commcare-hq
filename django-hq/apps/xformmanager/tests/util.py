from xformmanager.manager import *
from xformmanager.xformdef import *
from receiver.tests.submissions import *
import logging

def create_xsd_and_populate(xsd_file_name, xml_file_name=''):
    # Create a new form definition
    manager = XFormManager()
    
    f = open(os.path.join(os.path.dirname(__file__),xsd_file_name),"r")
    formdefmodel = manager.add_schema(xsd_file_name, f)
    f.close()
    if xml_file_name:
        populate(xml_file_name, manager)
    return formdefmodel

def populate(xml_file_name, manager=None):
    if xml_file_name is not None:
        # and input one xml instance
        #arguments: data_stream_pointer, formdef, formdefmodel_id, submission_id
        submission = create_fake_submission(xml_file_name)
        

def create_fake_submission(xml_file):
    # can't use get_full_path on the body since it's not relative to that file
    full_body_path = os.path.join(os.path.dirname(__file__), xml_file)
    submission = makeNewEntry(get_full_path('simple-meta.txt'), full_body_path)
    return submission.attachments.all()[0]
    