"""We put utility code in a separate package so that other tests 
   (such as xformmanager's) can use it without triggering 
   the receiver unit tests
"""
import os
from receiver import submitprocessor 
from domain.models import Domain
import hashlib

def get_full_path(file_name):
    '''Joins a file name with the directory of the current file
       to get the full path'''
    head, tail = os.path.split(os.path.dirname(__file__))
    return os.path.join( head,file_name )
    
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
    
    checksum = hashlib.md5(body).hexdigest()            
    new_submission = submitprocessor.new_submission(metahash, checksum, mockdomain)        
    submitprocessor.save_legacy_blob(new_submission, body)
    attachments = submitprocessor.handle_legacy_blob(new_submission)
    return new_submission
    
    


