from django.db import models
from datetime import datetime
from django.utils.translation import ugettext_lazy as _
from django.contrib.auth.models import Group, User
import uuid
import settings
from organization.models import *
import os

if not os.path.exists(settings.rapidsms_apps_conf['xformmanager']['xsd_repository_path']):
    os.mkdir(settings.rapidsms_apps_conf['xformmanager']['xsd_repository_path'])    
    
if not os.path.exists(settings.rapidsms_apps_conf['xformmanager']['csv_path']):
    os.mkdir(settings.rapidsms_apps_conf['xformmanager']['csv_path'])

if not os.path.exists(settings.rapidsms_apps_conf['xformmanager']['xsd_repository_path']):
    os.mkdir(settings.rapidsms_apps_conf['xformmanager']['xsd_repository_path'])


#import Group

class ElementDefData(models.Model):
    """ At such time as we start to store an edd for every node, we can use the following supporting xform types list
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
    form = models.ForeignKey('FormDefData')
    
    def __unicode__(self):
        return self.table_name

class FormDefData(models.Model):
    # a bunch of these fields have null=True to make unit testing easier
    # also, because creating a form defintion shouldn't be dependent on receing form through server
    uploaded_by = models.ForeignKey(ExtUser, null=True)
    
    submit_time = models.DateTimeField(_('Submission Time'), default = datetime.now())
    submit_ip = models.IPAddressField(_('Submitting IP Address'), null=True)
    bytes_received = models.IntegerField(_('Bytes Received'), null=True)
    
    # META fields to be placed here eventually
    #settings.XSD_REPOSITORY_PATH
    xsd_file_location = models.FilePathField(_('Raw XSD'), path=settings.rapidsms_apps_conf['xformmanager']['xsd_repository_path'], max_length=255, null=True)
    
    #form_name is used as the table name
    form_name = models.CharField(_('Fully qualified form name'),max_length=255, unique=True)
    form_display_name = models.CharField(_('Readable Name'),max_length=128, null=True)
    
    target_namespace = models.CharField(max_length=255, unique=True)
    date_created = models.DateField(auto_now=True)
    #group_id = models.ForeignKey(Group)
    #blobs aren't supported in django, so we just store the filename
    
    element = models.OneToOneField(ElementDefData, null=True)
    # formdefs have a one-to-one relationship with elementdefs
    # yet elementdefs have a form_id which points to formdef
    # without this fix, delete is deadlocked
    def delete(self): 
        self.element = None 
        self.save()
        super(FormDefData, self).delete()
    
    def __unicode__(self):
        return "XForm " + unicode(self.form_name)
    
    @property
    def get_domain(self):
        return self.uploaded_by.domain

class Metadata(models.Model):
    # DO NOT change the name of these fields or attributes - they map to each other
    # in fact, you probably shouldn't even change the order
    # (TODO - replace with an appropriate comparator object, so that the code is less brittle )
    fields = [ 'formname','formversion','deviceid','timestart','timeend','username','chw_id','uid' ]
    formname = models.CharField(max_length=255)
    formversion = models.CharField(max_length=255)
    deviceid = models.CharField(max_length=255)
    # do not remove default values, as these are currently used to discover field type
    timestart = models.DateTimeField(_('Time start form'), default = datetime.now())
    timeend= models.DateTimeField(_('Time end form'), default = datetime.now())
    username = models.CharField(max_length=255)
    chw_id = models.CharField(max_length=255)
    #unique id
    uid = models.CharField(max_length=32)
    # foreign key to the row in the generated data table
    # foreign key to the associated submission
    
    def __unicode__(self):
        return "Metadata " + unicode(self.name)
    


