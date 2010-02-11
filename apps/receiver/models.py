import uuid
import settings
import email
import logging
import string
import hashlib
import sys
import os
import traceback
from django.utils import simplejson
from random import choice
from datetime import datetime

from django.db import models
from django.db.models.signals import post_save
from django.utils.translation import ugettext_lazy as _
from django.core import serializers
from django.core.urlresolvers import reverse
from django.contrib.auth.models import User

from hq.models import *
from domain.models import Domain
from hq.utils import build_url

_XFORM_URI = 'xform'
_DUPLICATE_ATTACHMENT = "duplicate_attachment"
_RECEIVER = "receiver"

class Submission(models.Model):
    '''A Submission object.  Represents an instance of someone POST-ing something
       to our site.'''
    submit_time = models.DateTimeField(_('Submission Time'), default = datetime.now)
    transaction_uuid = models.CharField(_('Submission Transaction ID'), max_length=36, default=uuid.uuid1())    
    domain = models.ForeignKey(Domain, null=True)    
    submit_ip = models.IPAddressField(_('Submitting IP Address'))    
    checksum = models.CharField(_('Content MD5 Checksum'),max_length=32)    
    bytes_received = models.IntegerField(_('Bytes Received'))
    content_type = models.CharField(_('Content Type'), max_length=100)
    raw_header = models.TextField(_('Raw Header'))    
    raw_post = models.FilePathField(_('Raw Request Blob File Location'), match='.*\.postdata$', path=settings.RAPIDSMS_APPS['receiver']['xform_submission_path'], max_length=255, null=True)    
    authenticated_to = models.ForeignKey(User, null=True)

    class Meta:
        get_latest_by = 'submit_time'
    
    @property
    def num_attachments(self):
        return Attachment.objects.all().filter(submission=self).count()
    
    @property
    def xform(self):
        '''Returns the xform associated with this, defined by being the
           first attachment that has a content type of text/xml.  If no such
           attachments are found this will return nothing.
        '''
        attachments = self.attachments.order_by("id")
        for attachment in attachments:
            # we use the uri because the content_type can be either 'text/xml'
            # (if coming from a phone) or 'multipart/form-data'
            # (if coming from a webui)
            if attachment.attachment_uri == _XFORM_URI:
                return attachment
        return None
        
        
    class Meta:
        ordering = ('-submit_time',)
        verbose_name = _("Submission Log")        
        get_latest_by = "submit_time"
        
    def __unicode__(self):
        return "Submission " + unicode(self.submit_time)
    
    def delete(self, **kwargs):
        if self.raw_post is not None and os.path.exists(self.raw_post) and os.path.isfile(self.raw_post):
            os.remove(self.raw_post)
        else:
            logging.warn("Raw post not found on file system.")
        
        attaches = Attachment.objects.all().filter(submission = self)
        if len(attaches) > 0:
            for attach in attaches:
                attach.delete()      
        super(Submission, self).delete()
        
    def handled(self, handle_type, message=""):
        """Mark the submission as being handled in the way that is passed in.
           Returns the SubmissionHandlingOccurrence that is created."""
        return SubmissionHandlingOccurrence.objects.create(submission=self, 
                                                           handled=handle_type,
                                                           message=message)
    
    def unhandled(self, handle_type):
        """ Deletes the 'handled' reference (used when data is deleted) """
        try:
            SubmissionHandlingOccurrence.objects.get(submission=self, \
                                                     handled=handle_type).delete()
        except SubmissionHandlingOccurrence.DoesNotExist:
            return
    
    def is_orphaned(self):
        """Whether the submission is orphaned or not.  Orphanage is defined 
           by having no information about the submission being handled. This 
           explicitly should never include something that's a duplicate, since
           all dupes are explicitly logged as handled by this app.
        """
        # this property will be horribly inaccurate until we clear and resubmit everything 
        # in our already-deployed servers
        return len(SubmissionHandlingOccurrence.objects.filter(submission=self)) == 0 
        
    def is_deleted(self):
        '''Whether this has has been explicitly marked as deleted 
           in any handling app.
        '''
        all_delete_types = SubmissionHandlingType.objects.filter(method="deleted")
        return len(self.ways_handled.filter(handled__in=all_delete_types)) > 0
    
    def is_duplicate(self):
        """Whether the submission is a duplicate or not.  Duplicates 
           mean that at least one attachment from the submission was 
           the exact same (defined by having the same md5) as a previously
           seen attachment."""
        # TODO: There's two ways to do this: one relies on the post_save event to 
        # populate the handlers correctly.  The other would just call is_duplicate
        # on all the attachments.  I think either one would be fine, but since
        # one will work pre-migration while one will only work post migration
        # I'm TEMPORARILY going with the one that walks the attachments.
        # This is miserably slow (doing a full table scan for every submit) so 
        # should really move as soon as we migrate.
        
        # Correct implementation commented out until migration
        #for handled in SubmissionHandlingOccurrence.objects.filter(submission=self):
        #    if handled.handled.method == _DUPLICATE_ATTACHMENT:
        #        return True
        #return False
        for attach in self.attachments.all():
            if attach.is_duplicate():
                return True
        return False
    
    def export(self):
        """ walks through the submission and bundles it
        in an exportable format with the original submitting IP 
        and time, as well as a reference to the original post
        
        """
        #print "processing %s (%s)" % (self,self.raw_post)
        if self.raw_post is None:
            raise Submission.DoesNotExist("Submission (%s) has empty raw_post" % self.pk)
        if not os.path.exists(self.raw_post):
            raise Submission.DoesNotExist("%s could not be found" % self.raw_post)
        post_file = open(self.raw_post, "r")
        submit_time = str(self.submit_time)
        # first line is content type
        content_type = post_file.readline().split(":")[1].strip()
        # second line is content length
        content_length = post_file.readline().split(":")[1].strip()
        # third line is empty
        post_file.readline()
        # the rest is the actual body of the post
        headers = { "content-type" : content_type, 
                    "content-length" : content_length,
                    "time-received" : str(self.submit_time),
                    "original-ip" : str(self.submit_ip),
                    "domain" : self.domain.name
                   }
        # the format will be:
        # {headers} (dict)
        #           (empty line)
        # <body>   
        return simplejson.dumps(headers) + "\n\n" + post_file.read()


#dmyung 11/5/2009 - removing signal and refactor attachment processing to the submit processor
#post_save.connect(process_attachments, sender=Submission)

            
    
class Attachment(models.Model):
    '''An Attachment object, which is part of a submission.  Many submissions
       will only have one attachment, but multipart submissions will be broken
       into their individual attachments.'''
    
    submission = models.ForeignKey(Submission, related_name="attachments")
    attachment_content_type = models.CharField(_('Attachment Content-Type'),max_length=64)
    attachment_uri = models.CharField(_('File attachment URI'),max_length=255)
    filepath = models.FilePathField(_('Attachment File'),match='.*\.attach$',path=settings.RAPIDSMS_APPS['receiver']['xform_submission_path'],max_length=255)
    filesize = models.IntegerField(_('Attachment filesize'))
    checksum = models.CharField(_('Attachment MD5 Checksum'),max_length=32)
    
    def handled(self, handle_type, message=""):
        """ For now, handling any attachment is equivalent to handling the 
        submission instance. We can imagine changing this at some future date
        to use some other sort of heuristic for when a submission is 'handled'.
        
        """
        return self.submission.handled(handle_type, message)
    
    def unhandled(self, handle_type):
        """ Deletes the 'handled' reference for this attachment's submission"""
        self.submission.unhandled(handle_type)
    
    def is_xform(self):
        return self.attachment_uri == _XFORM_URI
    
    def get_media_url(self):
        basename = os.path.basename(self.filepath)
        return settings.MEDIA_URL + "attachment/" + basename

    def get_contents(self):
        """Get the contents for an attachment object, by reading (fully) the
           underlying file."""
        fin = None
        try:
            fin = open(self.filepath ,'r')
            return fin.read()
        except Exception, e:
            logging.error("Unable to open attachment %s. %s" % (self, e.message),
                          extra={"exception": e})
        finally:
            if fin:   fin.close()
        
    
    def delete(self, **kwargs):
        try:
            # if for some reason deleting the file fails,
            # we should still continue deleting the data model
            os.remove(self.filepath)
        except Exception, e:
            logging.warn(str(e))
        super(Attachment, self).delete()
    
    def has_duplicate(self):
        '''
        Checks if this has any duplicate submissions, 
        defined by having the same checksum, but a different
        id.
        '''
        return len(Attachment.objects.filter(checksum=self.checksum).exclude(id=self.id)) != 0
        
    def is_duplicate(self):
        '''
        Checks if this is a duplicate submission,
        defined by having other submissions with 
        the same checksum, but a different id, and 
        NOT being the first one
        '''
        all_matching_checksum = Attachment.objects.filter(checksum=self.checksum)
        if len(all_matching_checksum) <= 1:
            return False
        all_matching_checksum = all_matching_checksum.order_by("submission__submit_time").order_by("id")
        return self.id != all_matching_checksum.order_by("submission__submit_time").order_by("id")[0].id
    
    def has_linked_schema(self):
        '''
        Returns whether this submission has a linked schema, defined
        by having something in the xform manager that knows about this.
        '''
        # this method, and the one below are semi-dependant on the 
        # xformmanager app.  if that app is not running, this will
        # never be true but will still resolve.
        if self.get_linked_metadata():
            return True
        return False
    
    def get_linked_metadata(self):
        '''
        Returns the linked metadata for the form, if it exists, otherwise
        returns nothing.
        '''
        if hasattr(self, "form_metadata"):
            try:
                return self.form_metadata.get()
            except:
                return None
        return None
    
    def most_recent_annotation(self):
        """Get the most recent annotation of this attachment, if it exists"""
        if (self.annotations.count() > 0):
            return self.annotations.order_by("-date")[0]
    
    class Meta:
        ordering = ('-submission',)
        verbose_name = _("Submission Attachment")        
    
    def __unicode__(self):
        return "%s : %s"  % (self.id, self.attachment_uri)
    
    def display_string(self):
        return """Domain: %s - 
                  Attachment: %s - 
                  Submission: %s - 
                  Submit Time: %s - 
                  Content Type: %s - 
                  URI: %s - 
                  URL to view on server: %s
                  """  % \
                  (self.submission.domain, self.id, self.submission.id, 
                   self.submission.submit_time, self.attachment_content_type, 
                   self.attachment_uri, 
                   build_url(reverse('single_submission', args=(self.submission.id,))))
  

class Annotation(models.Model):
    """Annotate attachments."""
    # NOTE: we could make these total generic with django content-types, but
    # I think it will be easier to only annotate attachments.
    attachment = models.ForeignKey(Attachment, related_name="annotations")
    date = models.DateTimeField(default = datetime.now)
    text = models.CharField(max_length=255)
    user = models.ForeignKey(User)
    
    # eventually link to an outgoing sms message on the annotation.
    #sms_message = models.ForeignKey(OutgoingMessage, related_name="annotations", 
    #                                null=True, blank=True)
        
    # for threading these, for now this is unused
    parent = models.ForeignKey("self", related_name="children", null=True, blank=True)
    
    def __unicode__(self):
        return '"%s" by %s on %s' % (self.text, self.user, self.date.date())
 
    def to_html(self):
        return '<div class="annotation"><div class="annotation-date">%s</div><div class="annotation-body">%s</div></div>' %\
               (self.date.date(), self.text)
 
class SubmissionHandlingType(models.Model):
    '''A way in which a submission can be handled.  Contains a reference
       to both an app, that did the handling, and a method, representing
       how the app did something.  For example, one app could be "xformmanager" 
       and a way of handling could be "saved_form_data".
       If app.methodname is a valid python method, receiver will attempt
       to call it with the handling occurrence and a dictionary of additional
       parameters as the arguments, and if 
       the method returns an HttpResponse object that will override
       the default response.  See __init__.py in this module for an example.
    '''
    # todo? these model names are pretty long-winded 
    app = models.CharField(max_length=50)
    method = models.CharField(max_length=100)
    
    def __unicode__(self):
        return "%s: %s" % (self.app, self.method)
    
class SubmissionHandlingOccurrence(models.Model):
    """A class linking submissions to ways of handling them.  Other apps
       should create instances of this model by calling submission.handled()
       with the appropriate handling type as submissions are processed.
       An app creating an instance of this implies that the app somehow 
       'understood' the submission, so unparsed or error-full submisssions
       should not have instances of this."""
    # todo? these model names are pretty long-winded 
    submission = models.ForeignKey(Submission, related_name="ways_handled")
    handled = models.ForeignKey(SubmissionHandlingType)    
    
    # message allows any handler to add a short message that 
    # the receiver app will display to the user
    message = models.CharField(max_length=100, null=True, blank=True)
    


def log_duplicates(sender, instance, created, **kwargs): #get sender, instance, created
    '''A django post-save event that logs duplicate submissions to the
       handling log.'''
    # only log dupes on newly created attachments, not all of them
    if not created:
        return
    if instance.is_duplicate():
        try:
            error = "Got a duplicate attachment: %s." %\
                    (instance.display_string())
            logging.error(error)
            
            # also mark that we've handled this as a duplicate. 
            try:
                handle_type = SubmissionHandlingType.objects.get(app=_RECEIVER, method=_DUPLICATE_ATTACHMENT)
            except SubmissionHandlingType.DoesNotExist:
                handle_type = SubmissionHandlingType.objects.create(app=_RECEIVER, method=_DUPLICATE_ATTACHMENT)
            instance.submission.handled(handle_type)
        except Exception, e:
            logging.error("Problem logging a duplicate attachment: %s.  The error is: %s" %\
                          (instance.display_string(), e))
    
# Register to receive signals on every attachment save.
post_save.connect(log_duplicates, sender=Attachment)

