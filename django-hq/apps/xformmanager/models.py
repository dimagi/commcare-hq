from django.db import models, connection
from datetime import datetime
from django.utils.translation import ugettext_lazy as _
from django.contrib.auth.models import Group, User
from django.db.models.signals import post_save

from dbanalyzer import dbhelper
from receiver.models import Attachment
from organization.models import *
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
    xsd_file_location = models.FilePathField(_('Raw XSD'), path=settings.rapidsms_apps_conf['xformmanager']['xsd_repository_path'], max_length=255, null=True)
    
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
    
        
    def get_rows(self, column_filters={}, sort_column="id", sort_descending=True):
        '''Get rows associated with this form's schema.
           The column_filters parameter should take in column_name, value
           pairs to be used in a where clause.  The default parameters
           return all the rows in the schema, sorted by id, descending.'''
        
        return self._get_cursor(column_filters, sort_column, sort_descending).fetchall()
        
    
    def _get_cursor(self, column_filters={}, sort_column="id", sort_descending=True):
        '''Gets a cursor associated with a query against this table.  See
           get_rows for documentation of the parameters.'''
        
        sql = "SELECT * FROM %s " % self.table_name
        # add filtering
        if column_filters:
            first = True
            for col, value in column_filters.items():
                if first:
                    # this casts everything to a string.  verified
                    # to work for strings and integers, but might 
                    # not work for dates
                    to_append = " WHERE %s = '%s' " % (col, value)
                    first = False
                else:
                    to_append = " AND %s = %s " % (col, value)
                sql = sql + to_append
        
        desc = ""
        if sort_descending:
            desc = "desc"
        sql = sql + (" ORDER BY %s %s " % (sort_column, desc))
        cursor = connection.cursor()
        cursor.execute(sql)
        return cursor
    
    def get_column_names(self):
        '''Get all data rows associated with this form's schema
           (not including repeats)'''
        return [col[0] for col in self._get_cursor().description]

    
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
    # foreign key to the associated submission (from receiver app)
    submission = models.ForeignKey(Attachment, null=True)
    # foreign key to the row in the manually generated data table
    raw_data = models.IntegerField(_('Raw Data Id'), null=True)
    # foreign key to the schema definition (so can identify table and domain)
    formdefmodel = models.ForeignKey(FormDefModel, null=True)
    
    def __unicode__(self):
        list = ["%s: %s" % (name, getattr(self, name)) for name in self.fields]
        return "Metadata: " + ", ".join(list) 
    

class FormIdentifier(models.Model):
    '''An identifier for a form.  This is a way for a case to point at
       a particular form, using a particular column in that form.  These
       also have sequence ids so that you can define the ordering of a
       full listing of the data for a case'''
    
    form = models.ForeignKey(FormDefModel)
    identity_column = models.CharField(max_length=255)
    # the column that defines how sorting works.  if no sorting is 
    # defined the case will assume each member of identity_column
    # appears exactly once, and this may behave unexpectedly if that
    # is not true
    sorting_column = models.CharField(max_length=255, null=True, blank=True)
    # sort ascending or descending
    sort_descending = models.BooleanField(default=True)
    
    
    def get_uniques(self):
        '''Return a list of unique values contained in this column'''
        return self.form.db_helper.get_uniques_for_column(self.identity_column)
    
    def get_data_lists(self):
        '''Gets all rows per unique identifier, sorted by the default
           sorting column.  What is returned is a dictionary of 
           lists of lists of the form:
           { id_column_value_1: [[value_1, value_2, value_3...],
                                 [value_1, value_2, value_3...],
                                 ...],
             id_column_value_2: [value_1, value_2, value_3...],
             ...
           }
           Each inner list represents a row of the data in 
           that form corresponding to the id column.  The lists
           will be ordered by the sorting column. 
           '''
        if self.sorting_column:
            list = self.form.get_rows(sort_column=self.sorting_column, 
                                      sort_descending=self.sort_descending)
            
        else:
            # no sorting column, just get everything in an arbitrary order.  
            list = self.form.get_rows()
        
        id_index = self.form.get_column_names().index(self.identity_column)
        to_return = {}
        for row in list:
            id_value = row[id_index]
            if not to_return.has_key(id_value):
                to_return[id_value] = []
            to_return[id_value].append(row)
        return to_return
    
    
    def get_data_for_case(self, case_id):
        '''Gets the list of entries for a single case.'''
        
        filter_cols = {self.identity_column : case_id}
        if self.sorting_column:
            return self.form.get_rows(column_filters=filter_cols,
                                      sort_column=self.sorting_column, 
                                      sort_descending=self.sort_descending)
        else:
            return self.form.get_rows(column_filters=filter_cols)
    
    
    def get_data_maps(self):
        '''Gets one row per unique identifier, sorted by the default
           sorting column.  What is returned is a dictionary of 
           lists of dictionaries of the form 
           { id_column_value_1: [{data_column_1: value_1,
                                  data_column_2: value_2,
                                  ...
                                 },
                                 {data_column_1: value_1,
                                  data_column_2: value_2,
                                  ...
                                 },
                                 ...
                                ]
             id_column_value_2: {data_column_1: value_1,
                                 data_column_2: value_2,
                                 ...
                                }
             ...
           }
           '''
        data_lists = self.get_data_lists()
        to_return = {}
        columns = self.form.get_column_names()
        for id, list in data_lists.items():
            # magically zip these up in a dictionary
            to_return[id] = [dict(zip(columns, sub_list)) for sub_list in list]
        return to_return
    
    
    def __unicode__(self):
        return "%s: %s" % (self.form, self.identity_column)

class Case(models.Model):
    '''A Case is a collection of data that represents a logically cohesive
       unit.  A case could be a case of a disease (e.g. Malaria) or could
       be an entire patient record.  In X-Form land, cases are collections
       of X-Form schemas that are linked together by a common identifier.'''
    
    name = models.CharField(max_length=255)
    domain = models.ForeignKey(Domain)
    
    def __unicode__(self):
        return self.name
    
    @property
    def forms(self):
        '''Get all the forms that make up this case'''
        forms = self.form_data.all()
        return [col.form_identifier.form for col in\
                self.form_data.all().order_by("sequence_id")]
    
    @property
    def form_identifiers(self):
        '''Get all the form identifiers that make up this case'''
        return [col.form_identifier for col in\
                self.form_data.all().order_by("sequence_id")]
    
    def get_unique_ids(self):
        '''Get the unique identifiers across the contained forms'''
        to_return = []
        for form_identifier in self.form_identifiers:
            for value in form_identifier.get_uniques():
                if value not in to_return:
                    to_return.append(value)
        return to_return        
        
    def get_column_names(self):
        '''Get the full list of column names, for all the forms'''
        to_return = []
        for form in self.form_data.order_by('sequence_id'):
            for col in form.form_identifier.form.get_column_names():
                # todo: what should these really be to differentiate
                # between the different forms?  the form name 
                # is probably too long, and the display name
                # can be null.  the id and sequence are both 
                # alright.  going with id for now.
                to_return.append("%s_%s" % (col, form.sequence_id))
        return to_return        
        
    def get_topmost_data(self):
        '''Get the full topmost (single most recent per form) 
           data set of data for all the forms.  This
           Will be a dictionary of the id column to a single flat
           row aggregating the data across the forms.  E.g.:

           { id_column_value_1: [form1_value1, form1_value2, ...,
                                 form2_value1, form2_value2, ...,
                                 ...],
             id_column_value_1: [form1_value1, form1_value2, ...,
                                 form2_value1, form2_value2, ...,
                                 ...],
             
             ...
           }
           
           The number of items in each list will be equal to the 
           sum of the number of columns of all forms that are a 
           part of this case.
           '''
        to_return = {}
        unique_ids = self.get_unique_ids()
        for id in unique_ids:
            to_return[id] = [] 
        for form_id in self.form_identifiers:
            data_list = form_id.get_data_lists()
            for id in unique_ids:
                if id in data_list:
                    to_return[id].extend(data_list[id][0])
                else:
                    # there was no data for this id for this
                    # form so extend the list with empty values
                    to_return[id].extend([None]*form_id.form.column_count)
        return to_return
    
    def get_topmost_data_maps(self):
        '''Get the full topmost (single most recent per form) 
           data set of data for all the forms in 
           dictionary format.  This ill be a dictionary of 
           dictionaries with the id column as keys and a 
           dictionary aggregating the data across the forms.  E.g.:
           { id_column_value_1: {form1_datacolumn1: form1_value1,
                                 form1_datacolumn2: form1_value2,
                                 ...,
                                 form2_datacolumn1: form2_value1,
                                 form2_datacolumn2: form2_value2,
                                },
             id_column_value_2: {form1_datacolumn1: form1_value1,
                                 form1_datacolumn2: form1_value2,
                                 ...
                                }
             ...
           }
           The number of items in each dict will be equal to the 
           sum of the number of columns of all forms that are a 
           part of this case.
        '''
        lists = self.get_topmost_data()
        to_return = {}
        columns = self.get_column_names()
        for id, list in lists.items():
            # magically zip these up in a dictionary
            to_return[id] = dict(zip(columns, list))
        return to_return
    
    def get_data_for_case(self, case_id):
        '''Gets all data for a single case.  The return format is a 
           dictionary form identifier objects to lists of rows for 
           that form.  If there is no data for the form, the value
           in the dictionary will be an empty list.  Example:
           { form_id_1 : [], # no data for this form
             form_id_2 : [[value1, value2, value3, ... ],
                          [value1, value2, value3, ... ],
                          ...
                         ],
             ...
            }
           '''
        to_return = {}
        for form_id in self.form_identifiers:
            to_return[form_id] = form_id.get_data_for_case(case_id) 
        return to_return
    
    
    def get_all_data(self):
        '''Get the full data set of data for all the forms.  This  
           Will be a dictionary of the id column to a dictionary 
           that has the same structure as what would be generated 
           by get_data_for_case on that id.  Example:
           { case_id_1 : { form_id_1 : [], # no data for this form
                           form_id_2 : [[value1, value2, value3, ... ],
                                        [value1, value2, value3, ... ],
                                        ...
                                       ],
                           ...
                          },
             case_id_2 : ...
             ... 
            }
           '''
        to_return = {}
        unique_ids = self.get_unique_ids()
        for id in unique_ids:
            to_return[id] = {}
        for form_id in self.form_identifiers:
            data_list = form_id.get_data_lists()
            for id in unique_ids:
                if id in data_list:
                    to_return[id][form_id] = data_list[id]
                else:
                    to_return[id][form_id] = []
        return to_return
    
    def get_all_data_maps(self):
        '''Get the full data set of data for all the forms in  
           dictionary format. This is analogous to the 
           get_all_data method, and the corresponding _maps 
           methods.  
        '''
        to_return = {}
        unique_ids = self.get_unique_ids()
        for id in unique_ids:
            to_return[id] = {}
        for form_id in self.form_identifiers:
            data_maps = form_id.get_data_maps()
            for id in unique_ids:
                if id in data_maps:
                    to_return[id][form_id] = data_maps[id]
                else:
                    to_return[id][form_id] = []
        return to_return
        
class CaseFormIdentifier(models.Model):
    # yuck.  todo: come up with a better name.
    '''A representation of a FormIdentifier as a part of a case.  This 
       contains a link to the FormIdentifier, a sequence id, and a link
       to the case.'''
    form_identifier = models.ForeignKey(FormIdentifier)
    case = models.ForeignKey(Case, related_name="form_data")
    sequence_id = models.PositiveIntegerField()

    def __unicode__(self):
        return "%s %s: %s" % (self.case, self.sequence_id, self.form_identifier)

# process is here instead of views because in views it gets reloaded
# everytime someone hits a view and that messes up the process registration
# whereas models is loaded once
def process(sender, instance, **kwargs): #get sender, instance, created
    from manager import XFormManager
    xml_file_name = instance.filepath
    logging.debug("PROCESS: Loading xml data from " + xml_file_name)
    manager = XFormManager()
    table_name = manager.save_form_data(xml_file_name, instance)
    
# Register to receive signals from receiver
post_save.connect(process, sender=Attachment)

