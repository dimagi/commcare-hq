from xformmanager.manager import *
import logging

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
    formdefmodel = manager.add_schema(xsd_file_name, f)
    f.close()
    # fake out the form submission
    formdefmodel.submit_ip = '127.0.0.1'
    formdefmodel.bytes_received =  os.path.getsize(xsd_file_path)
    formdefmodel.form_display_name = 'mock display name'             
    formdefmodel.domain = domain
    formdefmodel.save()
    return formdefmodel

def populate(xml_file_name, domain=None, path=None):
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


""" The following is copied and pasted directly from receiver.util
It's in here because importing receiver.util automatically causes the 
receiver unit tests to run, which makes it hard to run xformmanager
unit tests in isolation

"""
import os
from receiver import submitprocessor 
from hq.models import Domain

def get_full_path(file_name):
    '''Joins a file name with the directory of the current file
       to get the full path'''
    return os.path.join(os.path.dirname(__file__),file_name)
    
def makeNewEntry(headerfile, bodyfile, domain=None):
    
    fin = open(headerfile,"r")
    meta= fin.read()
    fin.close()
    
    
    fin = open(bodyfile,"rb")
    body = fin.read()
    fin.close()
    
    metahash = eval(meta)
    if domain:
        mockdomain = domain
    elif Domain.objects.all().count() == 0:
        mockdomain = Domain(name='mockdomain')
        mockdomain.save()
    else:
        mockdomain = Domain.objects.all()[0]
    return submitprocessor.do_old_submission(metahash, body, domain=mockdomain)
