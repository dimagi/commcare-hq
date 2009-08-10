from django.db import models, connection
from datetime import datetime
from django.utils.translation import ugettext_lazy as _
from django.contrib.auth.models import Group, User
from django.db.models.signals import post_save

from graphing import dbhelper
from receiver.models import Attachment
from hq.models import *
import logging
import uuid
import settings
import os

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

    name = models.CharField(max_length=255, unique=True)
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
    
    def __unicode__(self):
        return self.table_name

class FormDefModel(models.Model):
    # a bunch of these fields have null=True to make unit testing easier
    # also, because creating a form defintion shouldn't be dependent on receing form through server
    uploaded_by = models.ForeignKey(ExtUser, null=True)
    
    # the domain this form is associated with, if any
    domain = models.ForeignKey(Domain, null=True, blank=True)
    
    submit_time = models.DateTimeField(_('Submission Time'), default = datetime.now())
    submit_ip = models.IPAddressField(_('Submitting IP Address'), null=True)
    bytes_received = models.IntegerField(_('Bytes Received'), null=True)
    
    # META fields to be placed here eventually
    #settings.XSD_REPOSITORY_PATH
    xsd_file_location = models.FilePathField(_('Raw XSD'), path=settings.RAPIDSMS_APPS['xformmanager']['xsd_repository_path'], max_length=255, null=True)
    
    # we should just call this table_name
    form_name = models.CharField(_('Fully qualified form name'),max_length=255, unique=True)
    form_display_name = models.CharField(_('Readable Name'),max_length=128, null=True)
    
    target_namespace = models.CharField(max_length=255, unique=True)
    date_created = models.DateField(auto_now=True)
    #group_id = models.ForeignKey(Group)
    #blobs aren't supported in django, so we just store the filename
    
    element = models.OneToOneField(ElementDefModel, null=True)
    
    # formdefs have a one-to-one relationship with elementdefs
    # yet elementdefs have a form_id which points to formdef
    # without this fix, delete is deadlocked
    def delete(self): 
        self.element = None 
        self.save()
        super(FormDefModel, self).delete()
    
    
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
        
    def get_rows(self, column_filters=[], sort_column="id", sort_descending=True):
        '''Get rows associated with this form's schema.
           The column_filters parameter should take in column_name, value
           pairs to be used in a where clause.  The default parameters
           return all the rows in the schema, sorted by id, descending.'''
        
        return self._get_cursor(column_filters, sort_column, sort_descending).fetchall()
        
    
    def _get_cursor(self, column_filters=[], sort_column="id", sort_descending=True):
        '''Gets a cursor associated with a query against this table.  See
           get_rows for documentation of the parameters.'''
        
        # Note that the data view is dependent on id being first
        sql = " SELECT s.*, su.submit_time FROM %s s " % self.table_name + \
              " JOIN xformmanager_metadata m ON m.raw_data=s.id " + \
              " JOIN receiver_attachment a ON m.submission_id=a.id " + \
              " JOIN receiver_submission su ON a.submission_id=su.id " + \
              " WHERE m.formdefmodel_id=%s " % self.pk
        # add filtering
        if column_filters:
            for filter in column_filters:
                if len(filter) != 3:
                    raise TypeError("_get_cursor expects column_filters of length 3 " + \
                        "e.g.['pk','=','3'] (only %s given)" % len(filter))
                if isinstance( filter[2],basestring ): 
                    to_append = " AND s.%s %s '%s' " % tuple( filter )
                else:
                    filter[2] = unicode(filter[2]) 
                    to_append = " AND s.%s %s %s " % tuple( filter )
                sql = sql + to_append
        desc = ""
        if sort_descending:
            desc = "desc"
        sql = sql + (" ORDER BY s.%s %s " % (sort_column, desc))
        cursor = connection.cursor()
        cursor.execute(sql)
        return cursor
    
    def get_column_names(self):
        '''Get all data rows associated with this form's schema
           (not including repeats)'''
        return [col[0] for col in self._get_cursor().description]

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

class Metadata(models.Model):
    # DO NOT change the name of these fields or attributes - they map to each other
    # in fact, you probably shouldn't even change the order
    # (TODO - replace with an appropriate comparator object, so that the code is less brittle )
    fields = [ 'formname','formversion','deviceid','timestart','timeend','username','chw_id','uid' ]
    formname = models.CharField(max_length=255, null=True)
    formversion = models.CharField(max_length=255, null=True)
    deviceid = models.CharField(max_length=255, null=True)
    # do not remove default values, as these are currently used to discover field type
    timestart = models.DateTimeField(_('Time start form'), default = datetime.now())
    timeend= models.DateTimeField(_('Time end form'), default = datetime.now())
    username = models.CharField(max_length=255, null=True)
    chw_id = models.CharField(max_length=255, null=True)
    #unique id
    uid = models.CharField(max_length=32, null=True)
    # foreign key to the associated submission (from receiver app)
    submission = models.ForeignKey(Attachment, null=True, related_name="form_metadata")
    # foreign key to the row in the manually generated data table
    raw_data = models.IntegerField(_('Raw Data Id'), null=True)
    # foreign key to the schema definition (so can identify table and domain)
    formdefmodel = models.ForeignKey(FormDefModel, null=True)
    
    def __unicode__(self):
        list = ["%s: %s" % (name, getattr(self, name)) for name in self.fields]
        return "Metadata: " + ", ".join(list) 
    
    def xml_file_location(self):
        return self.submission.filepath
    
    def get_submission_count(self, startdate, enddate):
        '''Gets the number of submissions matching this one that 
           fall within the specified date range.  "Matching" is 
           currently defined by having the same chw_id.'''
        # the matching criteria may need to be revised.
        return len(Metadata.objects.filter(chw_id=self.chw_id, 
                                           submission__submission__submit_time__gte=startdate,
                                           submission__submission__submit_time__lte=enddate))
        


# process is here instead of views because in views it gets reloaded
# everytime someone hits a view and that messes up the process registration
# whereas models is loaded once
def process(sender, instance, **kwargs): #get sender, instance, created
    if not instance.is_xform():
        return

    # yuck, this import is in here because they depend on each other
    from manager import XFormManager
    xml_file_name = instance.filepath
    logging.debug("PROCESS: Loading xml data from " + xml_file_name)
    
    # only run the XFormManager logic if the submission isn't a duplicate 
    if not instance.is_duplicate():
        # TODO: make this a singleton?  Re-instantiating the manager every
        # time seems wasteful
        manager = XFormManager()
        manager.save_form_data(xml_file_name, instance)
    else:
        logging.error("Got a duplicate duplicate submission in the xformmanager: %s. It is being ignored." % instance)
                
    
# Register to receive signals from receiver
post_save.connect(process, sender=Attachment)

