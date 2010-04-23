import logging

from domain.models import Domain
from xformmanager.models import FormDataColumn, FormDataGroup, FormDataPointer
from xformmanager.manager import *
from xformmanager.storageutility import StorageUtility
from receiver.models import Submission, Attachment
from receiver.tests.util import *
from reports.models import Case, CaseFormIdentifier, FormIdentifier


def clear_data():
    """Clear most of the data in the system: schemas,
       submissions, and attachments.  Useful in the 
       setup and/or teardown methods of tests.
    """
    su = StorageUtility()
    su.clear()
    Submission.objects.all().delete()
    Attachment.objects.all().delete()
    
def clear_group_data():
    """Clear out the form group objects"""
    FormDataGroup.objects.all().delete()
    FormDataColumn.objects.all().delete()
    FormDataPointer.objects.all().delete()
    
def clear_case_data():
    """Clear out the form group objects"""
    Case.objects.all().delete()
    CaseFormIdentifier.objects.all().delete()
    FormIdentifier.objects.all().delete()
    
    
    
def get_file(filename, path=None ):
    """ handles relative pathing of files """
    if not path:
        path = os.path.dirname(__file__)
    return os.path.join( path, filename )

def create_xsd_and_populate(xsd_file_name, xml_file_name='', domain=None, path=None):
    if domain:
        mockdomain = domain
    elif Domain.objects.all().count() == 0:
        mockdomain = Domain(name='mockdomain')
        mockdomain.save()
    else:
        mockdomain = Domain.objects.all()[0]    
    formdefmodel = create_xsd(xsd_file_name, mockdomain, path=path)
    populate(xml_file_name, mockdomain, path)
    return formdefmodel

def create_xsd(xsd_file_name, domain=None, path=None):
    if not path:
        path = os.path.dirname(__file__)
    xsd_file_path = os.path.join(path,xsd_file_name)
    if xsd_file_name is None:
        return None
    f = open(xsd_file_path,"r")
    manager = XFormManager()
    formdefmodel = manager.add_schema(xsd_file_name, f, domain)
    f.close()
    # fake out the form submission
    formdefmodel.submit_ip = '127.0.0.1'
    formdefmodel.bytes_received =  os.path.getsize(xsd_file_path)
    formdefmodel.form_display_name = 'mock display name'             
    formdefmodel.domain = domain
    formdefmodel.save()
    return formdefmodel

def populate(xml_file_name, domain=None, path=None):
    """ returns submission """
    if xml_file_name:
        return create_fake_submission(xml_file_name, domain, path)
        
def create_fake_submission(xml_file, domain, path=None):
    if not path:
        # can't use get_full_path on the body since it's not relative to that file
        # the default assumes it's relative to this file
        path = os.path.dirname(__file__)
    full_body_path = os.path.join(path, xml_file)
    submission = makeNewEntry(get_full_path('simple-meta.txt'), full_body_path, domain)
    return submission
