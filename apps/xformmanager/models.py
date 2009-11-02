import os
import sys
import uuid
import logging
import settings
import traceback
from django.utils import simplejson
from MySQLdb import IntegrityError

from django.db import models, connection
from datetime import datetime, timedelta
from django.utils.translation import ugettext_lazy as _
from django.contrib.auth.models import Group, User
from django.db.models.signals import post_save
from django.core.urlresolvers import reverse

from hq.models import *
from hq.utils import build_url
from hq.dbutil import get_column_names
from graphing import dbhelper
from receiver.models import Submission, Attachment, SubmissionHandlingType
from xformmanager.util import case_insensitive_iter, format_field, format_table_name
from xformmanager.xformdef import FormDef

class ElementDefModel(models.Model):
    # this class is really not used
    """ At such time as we start to store an edd for every node, 
        we can use the following supporting xform types list
    TYPE_CHOICES = (
        ('string', 'string'),
        ('integer', 'integer'),
        ('int', 'int'),
        ('decimal', 'decimal'),
        ('double', 'double'),
        ('float', 'float'),
        ('dateTime', 'dateTime'),
        ('date', 'date'),
        ('time', 'time'),
        ('gYear', 'gYear'),
        ('gMonth', 'gMonth'),
        ('gDay', 'gDay'),
        ('gYearMonth', 'gYearMonth'),
        ('gMonthDay', 'gMonthDay'),
        ('boolean', 'boolean'),
        ('base64Binary', 'base64Binary'),
        ('hexBinary', 'hexBinary'),
        ('anyURI', 'anyURI'),
        ('listItem', 'listItem'),
        ('listItems', 'listItems'),
        ('select1', 'select1'),
        ('select', 'select'),
        ('geopoint', 'geopoint')
    )
    """

    xpath = models.CharField(max_length=255)
    table_name = models.CharField(max_length=255, unique=True)
    # For now, store all allowable values/enum definitions in one table per form
    allowable_values_table = models.CharField(max_length=255, null=True)
    is_attribute = models.BooleanField(default=False)
    is_repeatable = models.BooleanField(default=False)
    #I don't think we fully support this yet
    #restriction = models.CharField(max_length=255)
    parent = models.ForeignKey("self", null=True)
    # Note that the following only works for models in the same models.py file
    form = models.ForeignKey('FormDefModel')
    
    class Meta:
        unique_together = ("xpath", "form")

    def __unicode__(self):
        return self.table_name

class FormDefModel(models.Model):
    # a bunch of these fields have null=True to make unit testing easier
    # also, because creating a form defintion shouldn't be dependent on receing form through server
    uploaded_by = models.ForeignKey(ExtUser, null=True)
    
    # the domain this form is associated with, if any
    domain = models.ForeignKey(Domain, null=True, blank=True)
    
    submit_time = models.DateTimeField(_('Submission Time'), default = datetime.now)
    submit_ip = models.IPAddressField(_('Submitting IP Address'), null=True)
    bytes_received = models.IntegerField(_('Bytes Received'), null=True)
    
    # META fields to be placed here eventually
    #settings.XSD_REPOSITORY_PATH
    xsd_file_location = models.FilePathField(_('Raw XSD'), path=settings.RAPIDSMS_APPS['xformmanager']['xsd_repository_path'], max_length=255, null=True)
    
    # we should just call this table_name
    form_name = models.CharField(_('Fully qualified form name'),max_length=255, unique=True)
    form_display_name = models.CharField(_('Readable Name'),max_length=128, null=True)
    
    target_namespace = models.CharField(max_length=255)
    version = models.IntegerField(null=True)
    uiversion = models.IntegerField(null=True)
    date_created = models.DateField(auto_now=True)
    #group_id = models.ForeignKey(Group)
    #blobs aren't supported in django, so we just store the filename
    
    element = models.OneToOneField(ElementDefModel, null=True)
    
    class Meta:
        unique_together = ("target_namespace", "version")

    def _get_xform_file_location(self):
        loc = self.xsd_file_location + str(".xform")
        if os.path.exists(loc):
            return loc
        return None
    xform_file_location = property(_get_xform_file_location)
    
    # formdefs have a one-to-one relationship with elementdefs
    # yet elementdefs have a form_id which points to formdef
    # without this fix, delete is deadlocked
    def delete(self): 
        self.element = None 
        self.save()
        super(FormDefModel, self).delete()
    
    @classmethod
    def create_models(cls, formdef):
        """Create FormDefModel and ElementDefModel objects for a FormDef
           object."""
        fdd = FormDefModel()
        table_name = format_table_name(formdef.target_namespace, formdef.version)
        fdd.name = str(formdef.name)
        fdd.form_name = table_name
        fdd.target_namespace = formdef.target_namespace
        fdd.version = formdef.version
        fdd.uiversion = formdef.uiversion
        
        try:
            fdd.save()
        except IntegrityError, e:
            raise IntegrityError( ("Schema %s already exists." % fdd.target_namespace ) + \
                                   " Did you remember to update your version number?")
        ed = ElementDefModel()
        ed.xpath=formdef.root.xpath
        ed.table_name = table_name
        ed.form = fdd
        ed.save()
        ed.parent = ed
        ed.save()
        
        fdd.element = ed
        fdd.save()
        return fdd
    
    @classmethod
    def get_model(cls, target_namespace, version=None):
        """Given a form and version get me that formdef model.
           If formdef could not be found, returns None
        """
        try:
            return FormDefModel.objects.get(target_namespace=target_namespace,
                                                    version=version)
        except FormDefModel.DoesNotExist:
            return None
    
    @classmethod    
    def get_formdef(cls, target_namespace, version=None):
        """Given an xmlns and version, return the FormDef object associated
           with it, or nothing if no match is found"""
        formdefmodel = FormDefModel.get_model(target_namespace, version)
        if formdefmodel:
            return formdefmodel.to_formdef()
    
    def to_formdef(self):
        """Convert this FormDefModel to a FormDef object."""
        if self.xsd_file_location is None:
            # I wonder if we should really fail this hard...
            raise IOError("Schema for form %s could not be found on the file system." % \
                          target_namespace)
        return FormDef.from_file(self.xsd_file_location)
    
    @classmethod
    def is_schema_registered(cls, target_namespace, version=None):
        """Given a form and version is that form registered """
        return FormDefModel.get_model(target_namespace, version) is not None
    
    @property
    def db_helper(self):
        '''Get a DbHelper connected to this form'''
        return dbhelper.DbHelper(self.table_name, self.form_display_name)
    
    @property
    def table_name(self):
        '''Get the table name used by this form'''
        return self.element.table_name
    
    
    
    @property
    def column_count(self):
        '''Get the number of columns in this form's schema 
          (not including repeats)'''
        return len(self._get_cursor().description)
    
        
    def get_row(self, id):
        '''Get a row, by ID.'''
        list = self.get_rows([['id','=',id]])
        if len(list) == 1:
            return list[0]
        elif not list:
            return None
        else:
            raise Exception("Multiple values for id %s found in form %s" % (id, self ))
        
    def get_rows(self, column_filters=[], sort_column="id", sort_descending=True,
                 blacklist=[]):
        '''Get rows associated with this form's schema.
           The column_filters parameter should take in column_name, operation,
           value triplets to be used in a where clause.  (e.g. ['pk','=','3']) 
           The default parameters return all the rows in the schema, sorted 
           by id, descending.'''
           
        username_col = self.get_username_column() 
        if username_col:
            for blacklisted_user in blacklist:
                column_filters.append((username_col, "<>", blacklisted_user))
        return self._get_cursor(column_filters, sort_column, sort_descending).fetchall()
        
    
    def _get_cursor(self, column_filters=[], sort_column="id", sort_descending=True):
        '''Gets a cursor associated with a query against this table.  See
           get_rows for documentation of the parameters.'''
        
        # Note that the data view is dependent on id being first
        sql = " SELECT s.*, su.submit_time FROM %s s " % self.table_name + \
              " JOIN xformmanager_metadata m ON m.raw_data=s.id " + \
              " JOIN receiver_attachment a ON m.attachment_id=a.id " + \
              " JOIN receiver_submission su ON a.submission_id=su.id " + \
              " WHERE m.formdefmodel_id=%s " % self.pk
        # add filtering
        if column_filters:
            for filter in column_filters:
                if len(filter) != 3:
                    raise TypeError("_get_cursor expects column_filters of length 3 " + \
                        "e.g.['pk','=','3'] (only %s given)" % len(filter))
                if isinstance( filter[2],basestring ):
                    # strings need to be quoted
                    if filter[0] == 'submit_time':
                        to_append = " AND su.%s %s '%s' " % tuple( filter )
                    else:
                        to_append = " AND s.%s %s '%s' " % tuple( filter )
                else:
                    # force non-strings to strings
                    filter[2] = unicode(filter[2]) 
                    to_append = " AND s.%s %s %s " % tuple( filter )
                sql = sql + to_append
        desc = ""
        if sort_descending:
            desc = "desc"
        sql = sql + (" ORDER BY %s %s " % (sort_column, desc))
        cursor = connection.cursor()
        cursor.execute(sql)
        return cursor
    
    def get_column_names(self):
        '''Get the column names associated with this form's schema.
        '''
        return get_column_names(self._get_cursor())

    def get_display_columns(self):
        '''
        Get all columns, in order, as display strings.
        '''
        # all this currently does is remove "meta" from the beginning 
        # of anything and replace underscores with spaces
        cols = self.get_column_names()
        to_return = []
        for col in cols:
            if col.startswith("meta_"):
                col = col[5:]
            to_return.append(col.replace("_", " "))
        return to_return
        
    
    def __unicode__(self):
        return self.form_name
    
    @property
    def get_domain(self):
        # this is left to make domains backwards compatible (?)
        # we can probably get rid of it, actually
        return self.domain
    
    def get_username_column(self):
        '''Get the column where usernames are stored.  This is used by the
           blacklist.  Returns nothing if no username column is known or
           found.'''
        # TODO: not hard code this.
        column = "meta_username"
        if column in self.get_column_names():
            return column
                
    
    def export(self):
        """ walks through all the registered form definitions and
        bundles them with the original xsd schema for resubmission
    
        """
        file_loc = self.xsd_file_location
        if not file_loc:
            logging.warn("Could not find xsd at %s" % self.xsd_file_location)
        else:
            headers = {
                "original-submit-time" : str(self.submit_time),
                "original-submit-ip" : str(self.submit_ip),
                "bytes-received" : self.bytes_received,
                "form-name" : self.form_name,
                "form-display-name" : self.form_display_name,
                "target-namespace" : self.target_namespace,
                "date-created" : str(self.date_created),
                "domain" : str(self.get_domain)
                }
            xsd_file = open(file_loc, "r")
            payload = xsd_file.read()
            xsd_file.close() 
            return simplejson.dumps(headers) + "\n\n" + payload
    
    def time_of_last_instance(self):
        """ returns the last time an instance was submitted to this schema """
        submit = Submission.objects.filter(attachments__form_metadata__formdefmodel=self).latest()
        if submit is None:
            return None
        return submit.submit_time

class Metadata(models.Model):
    # DO NOT change the name of these fields or attributes - they map to each other
    # in fact, you probably shouldn't even change the order
    # (TODO - replace with an appropriate comparator object, so that the code is less brittle )

    # instead of 'username' we should really be using chw_id
    required_fields = [ 'deviceid','timestart','timeend','username' ]
    
    # these are all the fields that we accept (though do not require)
    fields = ['deviceid','timestart','timeend','username','formname','formversion','chw_id','uid']
    
    # CZUE: 10-29-2009 I think formname and formversion should now be removed?
    formname = models.CharField(max_length=255, null=True)
    formversion = models.CharField(max_length=255, null=True)
    
    deviceid = models.CharField(max_length=255, null=True)
    # do not remove default values, as these are currently used to discover field type
    timestart = models.DateTimeField(_('Time start form'), default = datetime.now)
    timeend= models.DateTimeField(_('Time end form'), default = datetime.now)
    username = models.CharField(max_length=255, null=True)
    chw_id = models.CharField(max_length=255, null=True)
    #unique id
    uid = models.CharField(max_length=32, null=True)
    # foreign key to the associated submission (from receiver app)
    # this is currently required. if we decide to decouple this from receiver,
    # then remember to link metadata.delete() to submission.unhandled() 
    attachment = models.ForeignKey(Attachment, related_name="form_metadata")
    # foreign key to the row in the manually generated data table
    raw_data = models.IntegerField(_('Raw Data Id'), null=True)
    # foreign key to the schema definition (so can identify table and domain)
    formdefmodel = models.ForeignKey(FormDefModel, null=True)

    version = models.IntegerField(null=True)
    uiversion = models.IntegerField(null=True)
    
    def __str__(self):
        return unicode(self).encode('utf-8')

    def __unicode__(self):
        list = ["%s: %s" % (name, getattr(self, name)) for name in self.fields]
        return "Metadata: " + ", ".join(list) 
    
    def init(self, data_tree, target_namespace):
        """ Initializes a metadata object. We make this external to 'init'
        because it's useful for us to format data according to the object's
        instantiated data types (see format_field function below)
         
        Arguments: takes the 'root' element of an lxml etree object
        """
        meta_tree = None
        
        if data_tree is None:
            logging.error("Submitted form (%s) is empty!" % target_namespace)
            return
        # find meta node
        for data_child in case_insensitive_iter(data_tree, '{'+target_namespace+'}'+ "Meta" ):
            meta_tree = data_child
            break;
        if meta_tree is None:
            logging.error("No metadata found for %s" % target_namespace )
            return
        
        """ we do not use this for now since we are still sorting out whether to have
        uid or guid or whatever
        # <parse by schema tree>
        # this method silently discards metadata which it does not anticipate
        for field in Metadata.fields:
            data_element = None
            for data_child in case_insensitive_iter(meta_tree, '{'+target_namespace+'}'+ field ):
                data_element = data_child
                break;
            if data_element is None:
                logging.error("Submitted form (%s) is missing metadata field (%s)" % \
                            (target_namespace, field) )
                continue
            if data_element.text is None: 
                logging.error( ("Metadata %s in form (%s) should not be null!" % \
                             (field, target_namespace)) )
                continue
            value = format_field(self, field, data_element.text)
            setattr( self,field,value )
        # </parse by schema tree>
        """
        
        # <parse by instance tree>
        # this routine silently ignores metadata fields which are poorly formatted
        # parse the meta data (children of meta node)
        for element in meta_tree:
            # element.tag is for example <FormName>
            # todo: this comparison should be made much less brittle - replace with a comparator object?
            tag = self._strip_namespace( element.tag ).lower()
            if tag in Metadata.fields:
                # must find out the type of an element field
                value = format_field(self, tag, element.text)
                # the following line means "model.tag = value"
                if value is not None: setattr( self,tag,value )
        # </parse by instance tree>
        
        return
    
    def xml_file_location(self):
        return self.attachment.filepath
    
    def get_submission_count(self, startdate, enddate):
        '''Gets the number of submissions matching this one that 
           fall within the specified date range.  "Matching" is 
           currently defined by having the same chw_id.'''
        # the matching criteria may need to be revised.
        return len(Metadata.objects.filter(chw_id=self.chw_id, 
                                           attachment__submission__submit_time__gte=startdate,
                                           attachment__submission__submit_time__lte=enddate))

    
    def save(self, target_namespace, **kwargs):
        # override save to support logging of bad metadata as it comes in
        self._log_bad_metadata(target_namespace)
        super(Metadata, self).save(**kwargs)

    @property
    def domain(self):
        """Attempt to get the domain of this metadata, or return 
           nothing"""
        if self.formdefmodel:
            return self.formdefmodel.domain
        return None
    
    @property
    def submitting_reporter(self):
        """Look for matching reporter, defined as someone having the same chw_id
           in their profile, and being a part of the same domain"""
        if self.domain and self.username:
            try:
                return ReporterProfile.objects.get(domain=self.domain, 
                                                   chw_username=self.username).reporter
            except Exception, e:
                # any number of things could have gone wrong.  Not found, too
                # many found, some other random error.  But just fail quietly
                pass
        return None
        
    def _log_bad_metadata(self, target_namespace):
        # log errors when metadata not complete
        missing_required_fields = []
        null_required_fields = []
        for field in self.required_fields:
            if not hasattr(self, field):
                # this should never, ever happen. 'field' variables are wrong.
                missing_required_fields.append(field) 
            else:
                value = getattr(self, field)
                if value is None:
                    null_required_fields.append(field)
        if missing_required_fields or null_required_fields:
            null_msg = ""
            missing_msg = ""
            if null_required_fields:
                null_msg = "null fields: %s\n" % ",".join(null_required_fields)
            if missing_required_fields:
                missing_msg = "missing fields:" % ",".join(missing_required_fields)
            logging.error("""Bad metadata submission to schema %s
                             The attachment is %s
                             The errors are:\n%s%s""" % (target_namespace,
                                                         self.attachment.display_string(),
                                                         null_msg, missing_msg)) 

    def _strip_namespace(self, tag):
        i = tag.find('}')
        tag = tag[i+1:len(tag)]
        return tag


# process is here instead of views because in views it gets reloaded
# everytime someone hits a view and that messes up the process registration
# whereas models is loaded once
def process(sender, instance, created, **kwargs): #get sender, instance, created
    # only process newly created xforms, not all of them
    if not created:
        return
    
    if not instance.is_xform():
        return
    
    # yuck, this import is in here because they depend on each other
    from manager import XFormManager
    xml_file_name = instance.filepath
    logging.debug("PROCESS: Loading xml data from " + xml_file_name)
    
    # only run the XFormManager logic if the attachment isn't a duplicate 
    if not instance.is_duplicate():
        # TODO: make this a singleton?  Re-instantiating the manager every
        # time seems wasteful
        manager = XFormManager()
        try:
            manager.save_form_data(xml_file_name, instance)
        except Exception, e:
            type, value, tb = sys.exc_info()
            traceback_string = '\n'.join(traceback.format_tb(tb))
            # we use 'xform_traceback' insetad of traceback since
            # dan's custom logger uses 'traceback'
            logging.error(str(e) + ". %s" % \
                          instance.display_string(),
                          extra={'file_name':xml_file_name, \
                                 'xform_traceback':traceback_string} )
    else:
        pass
        
# Register to receive signals from receiver
post_save.connect(process, sender=Attachment)

class MetaDataValidationError(Exception):
    '''Exception to make dealing with meta data errors easier.
       See StorageUtility.get_meta_validation_issues for how
       this is used.'''
       
    def __init__(self, error_dict, form_display=None):
        self.form_display = form_display
        self.missing = []
        self.duplicate = []
        self.extra = []
        error_msgs = []
        for type, list in error_dict.items():
            setattr(self, type, list)
            error_msgs.append("%s fields: %s" % (type, ",".join(list)))
        self.error_string = "\n".join(error_msgs)
    
    def __str__(self):
        return unicode(self).encode('utf-8')
        
    def __unicode__(self):
        return "Errors for %s:\n%s" % (self.form_display, self.error_string) 
