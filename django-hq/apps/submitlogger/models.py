from django.db import models
from datetime import datetime
from django.utils.translation import ugettext_lazy as _
from django.core import serializers
import uuid
import settings
import email
import logging
import string
import hashlib
import sys
import os


class SubmitLog(models.Model):   
    submit_time = models.DateTimeField(_('Submission Time'), default = datetime.now())
    transaction_uuid = models.CharField(_('Submission Transaction ID'), max_length=36, default=uuid.uuid1())
    
    submit_ip = models.IPAddressField(_('Submitting IP Address'))    
    checksum = models.CharField(_('Content MD5 Checksum'),max_length=32)    
    bytes_received = models.IntegerField(_('Bytes Received'))
    raw_header = models.TextField(_('Raw Header'))    
    raw_post = models.FilePathField(_('Raw Request Blob'), match='.*\.postdata$', path=settings.XFORM_SUBMISSION_PATH, max_length=255)    
        
    class Meta:
        ordering = ('-submit_time',)
        verbose_name = _("Submission Log")        
        get_latest_by = "submit_time"
        
    def __unicode__(self):
        return "Submission " + unicode(self.submit_time)
    def save(self, **kwargs):        
        super(SubmitLog, self).save()
        self.process_attachments()
    
    def delete(self, **kwargs):        
        os.remove(self.raw_post)
        
        attaches = Attachment.objects.all().filter(submission = self)
        if len(attaches) > 0:
            for attach in attaches:
                attach.delete()
                        
        super(SubmitLog, self).delete()
        
    
    def process_attachments(self):
        """Process attachments for a given submission blob.
        Will try to use the email parsing library to get all the MIME content from a given submission
        And write to file and make new Attachment entries linked back to this SubmitLog"""
        fin = open(self.raw_post,'rb')
        body = fin.read()        
        fin.close()
        #print body[0:500]
        try:
            parsed_message = email.message_from_string(body)   
            
            for part in parsed_message.walk():
               print "CONTENT-TYPE: " + str(part.get_content_type())     
               if part.get_content_type() == 'multipart/mixed':
                   #it's a multipart message, oh yeah
                   print "multipart: "
                   #print part['Content-ID']
                   #continue
               else:                   
                   new_attach= Attachment()
                   new_attach.submission = self
                   new_attach.attachment_content_type=part.get_content_type()
                   if part.get_content_type() == 'text/xml':                       
                       new_attach.attachment_uri = 'xform'
                       filename='-xform.xml'
                   else:
                       print 'not xml: ' + part['Content-ID'] 
                       new_attach.attachment_uri = part['Content-ID']
                       filename='-%s' % os.path.basename(new_attach.attachment_uri)
                       
                   payload = part.get_payload()
                   new_attach.filesize = len(payload)
                   new_attach.checksum = hashlib.md5(payload).hexdigest()
                   fout = open(os.path.join(settings.ATTACHMENTS_PATH,self.transaction_uuid + filename),'wb')
                   fout.write(payload)
                   fout.close() 
                   new_attach.filepath = os.path.join(settings.ATTACHMENTS_PATH,self.transaction_uuid + filename)
                   new_attach.save()                
                   print "save complete"  
                   #json = serializers.serialize('json',[new_attach])
                   #print json 
        except:
            logging.error("error parsing attachments") 
            logging.error("error parsing attachments: Exception: " + str(sys.exc_info()[0]))
            print "error parsing attachments: Exception: " + str(sys.exc_info()[0])
            logging.error("error parsing attachments: Traceback: " + str(sys.exc_info()[1]))
            print "error parsing attachments: Traceback: " + str(sys.exc_info()[1])

    
    
class Attachment(models.Model):
    submission = models.ForeignKey(SubmitLog)
    attachment_content_type = models.CharField(_('Attachment Content-Type'),max_length=64)
    attachent_uri = models.CharField(_('File attachment URI'),max_length=255)
    filepath = models.FilePathField(_('Attachment File'),match='.*\.attach$',path=settings.XFORM_SUBMISSION_PATH,max_length=255)
    filesize = models.IntegerField(_('Attachment filesize'))
    checksum = models.CharField(_('Attachment MD5 Checksum'),max_length=32)
    
    def delete(self, **kwargs):       
        os.remove(self.filepath)        
        super(Attachment, self).delete()
    
    class Meta:
        ordering = ('-submission',)
        verbose_name = _("Submission Attachment")        
    def __unicode__(self):
        return "Attachment " + unicode(self.uri)