"""
Given an xform definition, storageutility generates dynamic data tables.
Given an xml instance, storeagutility populates the data tables.

Basically, storageutility abstracts away all interaction with the database,
and it only knows about the data structures in xformdef.py
"""

import re
import os
import sys
import logging
import settings
import string
import shutil
import tempfile
from datetime import datetime, timedelta

from stat import S_ISREG, ST_MODE
from lxml import etree
from MySQLdb import IntegrityError

from django.db import connection, transaction, DatabaseError

from xformmanager.models import ElementDefModel, FormDefModel, Metadata
from xformmanager.util import *
from xformmanager.xformdef import FormDef
from xformmanager.xmlrouter import process
from receiver.models import SubmissionHandlingOccurrence, SubmissionHandlingType


# The maximum length a field is allowed to be.  Column names will get truncated
# to this length if they are longer than it.
_MAX_FIELD_NAME_LENTH = 64

class StorageUtility(object):
    """This class handles everything that touches the database - both form and
       instance data."""
    
    # should pull this out into a rsc file...  (CZUE: huh?)
    
    def __init__(self):
        # our own, transient data structure
        self.formdef = ''
        # the persistent django model of this form
        self.formdefmodel = None
    
    @transaction.commit_on_success
    def add_schema(self, formdef):
        """Given a xsd schema, create the django models and database
           tables reqiured to submit data to that form."""
        formdef.force_to_valid()
        formdefmodel = FormDefModel.create_models(formdef)
        self.formdefmodel = formdefmodel
        self.formdef = formdef 
        queries = XFormDBTableCreator( self.formdef, self.formdefmodel ).create()
        self._execute_queries(queries)
        return formdefmodel
    
    def save_form_data(self, attachment):
        """The entry point for saving form data from an attachment.
        
           returns True on success and false on fail."""
        
        xml_file_name = attachment.filepath
        f = open(xml_file_name, "r")
        # should match XMLNS
        xmlns, version = self.get_xmlns_from_instance(f)
        # If there is a special way to route this form, based on the xmlns
        # then do so here. 
        # czue: this is probably not the most appropriate place for this logic
        # but it keeps us from having to parse the xml multiple times.
        process(attachment, xmlns, version)
        try:
            formdefmodel = FormDefModel.objects.get(domain=attachment.submission.domain,
                                                    target_namespace=xmlns, version=version)
            
        except FormDefModel.DoesNotExist:
            raise self.XFormError("XMLNS %s could not be matched to any registered formdefmodel in %s." % (xmlns, attachment.submission.domain))
        if formdefmodel.xsd_file_location is None:
            raise self.XFormError("Schema for form %s could not be found on the file system." % formdefmodel[0].id)
        formdef = self.get_formdef_from_schema_file(formdefmodel.xsd_file_location)
        self.formdef = formdef
        
        f.seek(0,0)
        status = self._save_form_data_matching_formdef(f, formdef, formdefmodel, attachment)
        f.close()
        return status
    
    
   	
    @transaction.commit_on_success
    def _save_form_data_matching_formdef(self, data_stream_pointer, formdef, formdefmodel, attachment):
        """ returns True on success """
        
        logging.debug("StorageProvider: saving form data")
        data_tree = self._get_data_tree_from_stream(data_stream_pointer)
        
        populator = XFormDBTablePopulator( formdef, formdefmodel )
        queries = populator.populate( data_tree)
        if not queries:
            # we cannot put this check queries_to_populate (which is recursive)
            # since this is only an error on the top node
            raise TypeError("save_form_data called with empty form data")
        if not populator.errors.is_empty():
            if len(populator.errors.missing)>0:
                # this is quite common. esp. for metadata fields
                logging.info( "XForm instance is missing fields %s" % \
                              populator.errors.str('Missing') )
            elif len(populator.errors.bad_type)>0:
                raise populator.errors
            # TODO - add handlers for errors.duplicate and errors.extra
            # once those are implemented
        new_rawdata_id = queries.execute_insert()
        
        metadata_model = self._create_metadata(data_tree, formdefmodel, attachment, new_rawdata_id)
        
        # Add a "handled" flag that will eventually allow the receiver app 
        # to respond meaningfully about how the posting was handled
        startdate = datetime.now().date() 
        enddate = startdate + timedelta(days=1)
        message = metadata_model.get_submission_count(startdate, enddate)
        metadata_model.attachment.handled(get_instance_data_handle_type(), message)
        return True
    
    def _get_data_tree_from_stream(self, stream):
        tree=etree.parse(stream)
        return tree.getroot()
    
    def _get_data_tree_from_file(self, file_name):
        fin = open(file_name, 'r')
        root = self._get_data_tree_from_stream(fin)
        fin.close()
        return root
    
    def _create_metadata(self, data_tree, formdefmodel, attachment, rawdata_id):
        metadata_model = Metadata()
        version = case_insensitive_attribute(data_tree, "version")
        if version and version.strip().isdigit():
            metadata_model.version = version.strip()
        uiversion = case_insensitive_attribute(data_tree, "uiversion")
        if uiversion and uiversion.strip().isdigit():
            metadata_model.uiversion = uiversion.strip()
        metadata_model.init( data_tree, self.formdef.target_namespace )
        metadata_model.formdefmodel = formdefmodel
        metadata_model.attachment = attachment
        metadata_model.raw_data = rawdata_id
        metadata_model.save(self.formdef.target_namespace)        
        return metadata_model
    
    def get_formdef_from_schema_file(self, xsd_file_location):
        g = open( xsd_file_location ,"r")
        formdef = FormDef(g)
        formdef.force_to_valid()
        g.close()
        self.formdef = formdef
        return formdef
    
    # note that this does not remove the file from the filesystem 
    # (by design, for security)
    @transaction.commit_on_success
    def remove_instance_matching_schema(self, formdef_id, instance_id, remove_submission=False):
        fdm = FormDefModel.objects.get(pk=formdef_id)
        edm_id = fdm.element.id
        edm = ElementDefModel.objects.get(pk=edm_id)
        self._remove_instance_inner_loop(edm, instance_id)
        try:
            meta = Metadata.objects.get(raw_data=instance_id, formdefmodel=formdef_id)
        except Metadata.DoesNotExist:
            # not a problem since this simply means the data was 
            # never successfully registered
            return
        
        # markup the attachment as intentionally deleted by xformmanager
        meta.attachment.handled(get_deleted_handle_type())
        if remove_submission:
            meta.attachment.submission.delete()
        remove_metadata(meta)

    def _remove_instance_inner_loop(self, elementdef, instance_id):
        edms = ElementDefModel.objects.filter(parent=elementdef)
        cursor = connection.cursor()
        for edm in edms:
            cursor.execute( " select id, parent_id from " + edm.table_name + \
                            " where parent_id = %s ", [instance_id] )
            rows = cursor.fetchall()
            if rows:
                for row in rows:
                    self._remove_instance_inner_loop( edm, row[0] )
                query = " delete from " + edm.table_name + " where parent_id = %s "
                cursor.execute(query , [instance_id] )
        cursor.execute( " delete from " + elementdef.table_name + " where id = %s ", [instance_id] )

    @transaction.commit_on_success
    def remove_schema(self, id, remove_submissions=False, delete_xml=True):
        try:
            schema_to_remove = FormDefModel.objects.get(id=id)
        except FormDefModel.DoesNotExist:
            logging.error("  Schema with id %s could not be found. Not deleted." % id)
            return    
        # must remove tables first since removing form_meta automatically deletes some tables
        self._remove_form_tables(schema_to_remove)
        self._remove_form_models(schema_to_remove, remove_submissions, delete_xml)
        # when we delete formdefdata, django automatically deletes all associated elementdefdata
    
    # make sure when calling this function always to confirm with the user
    def clear(self, remove_submissions=True, delete_xml=True):
        """ removes all schemas found in XSD_REPOSITORY_PATH
            and associated tables. 
            If delete_xml is true (default) it also deletes the 
            contents of XFORM_SUBMISSION_PATH.        
        """
        self._remove_form_tables()
        self._remove_form_models(remove_submissions=remove_submissions, delete_xml=delete_xml)
        # when we delete formdefdata, django automatically deletes all associated elementdefdata
        
        if delete_xml:
            # drop all xml data instance files stored in XFORM_SUBMISSION_PATH
            for file in os.listdir( settings.RAPIDSMS_APPS['receiver']['xform_submission_path'] ):
                file = os.path.join( settings.RAPIDSMS_APPS['receiver']['xform_submission_path'] , file)
                logging.debug(  "Deleting " + file )
                stat = os.stat(file)
                if S_ISREG(stat[ST_MODE]) and os.access(file, os.W_OK):
                    os.remove( file )
                else:
                    logging.debug(  "  WARNING: Permission denied to access " + file )
                    continue
    
    class XFormError(SyntaxError):
        """ Generic error for XFormManager """
        pass
    
    def _execute_queries(self, queries):
        # todo - rollback on fail
        if queries is None or len(queries) == 0:
            logging.error("xformmanager: storageutility - xform " + self.formdef.target_namespace + " could not be parsed")
            return
        logging.debug(queries)
        cursor = connection.cursor()
        if queries.count(';') > 0:
            simple_queries = queries.split(';')
            for query in simple_queries: 
                if len(query)>0:
                    try: 
                        cursor.execute(query)
                    except Exception, e:
                        logging.error("problem executing query: %s.  %s" % (query, e))
                        raise
        else:
            cursor.execute(queries)            
    
    def _remove_form_models(self,form=None, remove_submissions=False, delete_xml=True):
        """Drop all schemas, associated tables, and files."""
        if form == None:
            fdds = FormDefModel.objects.all().filter()
        else:
            fdds = [form]            
        for fdd in fdds:
            if delete_xml:
                file = fdd.xsd_file_location
                if file is not None:
                    logging.debug(  "  removing file " + file )
                    if os.path.exists(file):
                        os.remove(file)
                    else:
                        logging.warn("Tried to delete schema file: %s but it wasn't found!" % file)
            
            self._drop_form_metadata(form, remove_submissions)
            
            logging.debug(  "  deleting form definition for " + fdd.target_namespace )
            fdd.delete()


    def _drop_form_metadata(self, form, remove_submissions):
        all_meta = Metadata.objects.filter(formdefmodel=form)
        for meta in all_meta:
            if remove_submissions:
                meta.attachment.submission.delete()
            remove_metadata(meta)
        
    # in theory, there should be away to *not* remove elemenetdefdata when deleting formdef
    # until we figure out how to do that, this'll work fine
    def _remove_form_tables(self,form=None):
        # drop all element definitions and associated tables
        # the reverse ordering is a horrible hack (but efficient) 
        # to make sure we delete children before parents
        if form == None:
            edds = ElementDefModel.objects.all().filter().order_by("-table_name")
        else:
            edds = ElementDefModel.objects.all().filter(form=form).order_by("-table_name")
        for edd in edds:
            logging.debug(  "  deleting data table:" + edd.table_name )
            if self._table_exists(edd.table_name):
                self._drop_table(edd.table_name)
            else: 
                logging.warn("Tried to delete %s table, but it wasn't there!" % edd.table_name)

    def _table_exists(self, table_name):
        '''Check if a table exists'''
        cursor = connection.cursor()
        cursor.execute("show tables like '%s'" % table_name)
        return len(cursor.fetchall()) == 1
        
    def _drop_table(self, table_name):
        '''Drop a table'''
        cursor = connection.cursor()
        cursor.execute("drop table %s" % table_name)
        
    #temporary measure to get target form
    # todo - fix this to be more efficient, so we don't parse the file twice
    def get_xmlns_from_instance(self, stream):
        xml_string = get_xml_string(stream)
        try:
            root = etree.XML(xml_string)
        except etree.XMLSyntaxError:
            raise self.XFormError("XML Syntax Error")
        r = re.search('{[a-zA-Z0-9_\-\.\/\:]*}', root.tag)
        if r is None:
            raise self.XFormError("NO XMLNS FOUND IN SUBMITTED FORM")
        xmlns = r.group(0).strip('{').strip('}')
        version = case_insensitive_attribute(root, "version")
        if version and version.strip().isdigit():
            return (xmlns, version.strip())
        return (xmlns, None)

class Query(object):
    """ stores all the information needed to run a query """
    
    def __init__(self, table_name='', field_value_dict={}, child_queries=[]): 
        self.table_name = table_name # string
        self.field_value_dict = field_value_dict # list of strings
        self.child_queries = child_queries # list of Queries
        self.parent_id = 0
    
    @transaction.commit_on_success
    def execute_insert(self):
        new_id = -1
        if len( self.field_value_dict ) > 0:
            query_string = "INSERT INTO " + self.table_name + " (";
    
            for field in self.field_value_dict:
                query_string = query_string + field + ", "
            query_string = self._trim2chars( query_string )
            if self.parent_id > 0: query_string = query_string + ", parent_id"
    
            query_string = query_string + ") VALUES( "

            # we use c-style substitution to enable django-built-in
            # sql-injection protection
            for value in self.field_value_dict:
                query_string = query_string + "%s, "
            query_string = self._trim2chars( query_string )
            if self.parent_id > 0: query_string = query_string + ", " + str(self.parent_id)
            query_string = query_string +  ");"

            values = []
            for value in self.field_value_dict:
                values = values + [ self.field_value_dict[ value ] ]
                
            new_id = self._execute(query_string, values)
        for child_query in self.child_queries:
            child_query.execute_insert()
        return new_id
    
    def _execute(self, queries, values):
        # todo - rollback on fail
        if queries is None or len(queries) == 0:
            logging.error("xformmanager: storageutility - xform " + self.formdef.target_namespace + " could not be parsed")
            return
        
        cursor = connection.cursor()
        if settings.DATABASE_ENGINE=='mysql':
            cursor.execute(queries, values)
            query = "SELECT LAST_INSERT_ID();"
            cursor.execute(query)
        else:
            cursor.execute(queries, values)
            query = "SELECT LAST_INSERT_ROWID()"
            cursor.execute(query)
        row = cursor.fetchone()
        if row is not None:
            return row[0]
        return -1
        
    def _trim2chars(self, string):
        return string[0:len(string)-2]

class XFormProcessor(object):
    """ Some useful utilities for any inheriting xformprocessor about how to deal with data """
    
    META_FIELDS = ['meta_formname','meta_commcareversion','meta_formversion','meta_deviceid',
                   'meta_timestart','meta_timeend','meta_username','meta_chw_id','meta_uid']
    
    def _hack_to_get_cchq_working(self, name):
                
        prefix = sanitize (self.formdef.name) + "_"
        
        if name[0:len(prefix)] == prefix:
            name = name[len(prefix)+1:len(name)]
        splits = name.split('_')
        endsplit = splits[-2:]
        if self.META_FIELDS.count('_'.join(endsplit)) == 1:
            return '_'.join(endsplit)
        
        return name

class XFormDBTableCreator(XFormProcessor):
    """This class is responsible for parsing a schema and generating the corresponding
       db tables dynamically.
    
       If there are errors, these errors will be stored in self.errors
    """

    # Data types taken from mysql. 
    # This should really draw from django built-in utilities which are database independent. 
    XSD_TO_MYSQL_TYPES = {
        'string':'VARCHAR(255)',
        'integer':'INT(11)',
        'int':'INT(11)',
        'decimal':'DECIMAL(5,2)',
        'double':'DOUBLE',
        'float':'DOUBLE',
        'datetime':'DATETIME', # string
        'date':'DATE', # string
        'time':'TIME', # string
        'gyear':'INT(11)',
        'gmonth':'INT(11)',
        'gday':'INT(11)',
        'gyearmonth':'INT(11)',
        'gmonthday':'INT(11)',
        'boolean':'TINYINT(1)',
        'base64binary':'DOUBLE', #i don't know...
        'hexbinary':'DOUBLE', #..meh.
        'anyuri':'VARCHAR(200)', # string
        'default':'VARCHAR(255)',
    } 

    XSD_TO_DEFAULT_TYPES = { #sqlite3 compliant
        'string':'VARCHAR(255)',
        'integer':'INT(11)',
        'int':'INT(11)',
        'decimal':'DECIMAL(5,2)',
        'double':'DOUBLE',
        'float':'DOUBLE',
        'datetime':'DateField', # string
        'date':'DateField', # string
        'time':'DateField', # string
        'gyear':'INT(11)',
        'gmonth':'INT(11)',
        'gday':'INT(11)',
        'gyearmonth':'INT(11)',
        'gmonthday':'INT(11)',
        'boolean':'TINYINT(1)',
        'base64binary':'DOUBLE', #i don't know...
        'hexbinary':'DOUBLE', #..meh.
        'anyuri':'VARCHAR(200)', # string
        'default':'VARCHAR(255)',
    } 

    def __init__(self, formdef, formdefmodel):
        """formdef - in memory transition object
           formdefmodel - django model which exists for each schema registered
        """
        self.formdef = formdef
        self.formdefmodel = formdefmodel
        self.errors = XFormErrors(formdef.target_namespace)
    
    def create(self):
        return self.queries_to_create_instance_tables( self.formdef, 
                                                       self.formdefmodel.element.id, 
                                                       self.formdef.name, self.formdef.name, self.formdefmodel.domain)
        
    # TODO - this should be cleaned up to use the same Query object that populate_instance_tables uses
    # (rather than just passing around tuples of strings)
    def queries_to_create_instance_tables(self, elementdef, parent_id, parent_name='', parent_table_name='', domain=None):
        
        table_name = format_table_name( formatted_join(parent_name, elementdef.name), self.formdef.version, self.formdef.domain_name )
        
        (next_query, fields) = self._create_instance_tables_query_inner_loop(elementdef, parent_id, parent_name, parent_table_name )
        # add this later - should never be called during unit tests
        if not fields: return next_query
        
        queries = ''
        if settings.DATABASE_ENGINE=='mysql' :
            queries = "CREATE TABLE "+ table_name +" ( id INT(11) NOT NULL AUTO_INCREMENT PRIMARY KEY, "
        else:
            queries = "CREATE TABLE "+ table_name +" ( id INTEGER PRIMARY KEY, "
        
        if len(fields[0]) == 1:
            queries = queries + str(fields)
        else:
            for field in fields:
                if len(field)>0:
                    queries = queries + str(field)
        
        # we don't really need a parent_id in our top-level table...
        # should be NOT NULL?
        if parent_name is not '':
            if settings.DATABASE_ENGINE=='mysql' :
                queries = queries + " parent_id INT(11), "
                queries = queries + " FOREIGN KEY (parent_id) REFERENCES " + \
                                    format_table_name(parent_table_name, self.formdef.version, self.formdef.domain_name) + \
                                    "(id) ON DELETE SET NULL" 
            else:
                queries = queries + " parent_id REFERENCES " + \
                                    format_table_name(parent_table_name, self.formdef.version, self.formdef.domain_name) + \
                                    "(id) ON DELETE SET NULL"
        else:
            queries = self._trim2chars(queries)

        
        # most of the time, we rely on global mysql config in my.conf/ini
        end_query = ");"
        
        # we only specify default engine and character set if it's clear that
        # we are already doing something against the global config
        # (i.e. we're settings database_options in settings.py)
        if hasattr(settings,'DATABASE_OPTIONS') and \
            'init_command' in settings.DATABASE_OPTIONS:
                if 'innodb' in settings.DATABASE_OPTIONS['init_command'].lower():
                    end_query = ") ENGINE=InnoDB;"
                elif 'myisam' in settings.DATABASE_OPTIONS['init_command'].lower():
                    end_query = ") ENGINE=MyISAM;"
        queries = queries + end_query + next_query
        return queries
    
    def _create_instance_tables_query_inner_loop(self, elementdef, parent_id, 
                                                  parent_name='', parent_table_name=''):
      """ This is 'handle' instead of 'create'(_children_tables) because not only 
          are we creating children tables, we are also gathering/passing 
          children/field information back to the parent. 
      """
      
      if not elementdef: return
      local_fields = [];
      
      next_query = ''
      if elementdef.is_repeatable and len(elementdef.child_elements)== 0 :
          return (next_query, self._db_field_definition_string(elementdef) )
      for child in elementdef.child_elements:
          # put in a check for root.isRepeatable
          next_parent_name = formatted_join(parent_name, elementdef.name)
          if child.is_repeatable :
              # repeatable elements must generate a new table
              if parent_id == '':
                  ed = ElementDefModel(form_id=self.formdefmodel.id, xpath=child.xpath, 
                                       table_name = format_table_name( formatted_join(parent_name, child.name), self.formdef.version, self.formdef.domain_name) ) #should parent_name be next_parent_name?
                  ed.save()
                  ed.parent = ed
              else:
                  ed = ElementDefModel(parent_id=parent_id, form=self.formdefmodel, xpath=child.xpath, 
                                  table_name = format_table_name( formatted_join(parent_name, child.name), self.formdef.version, self.formdef.domain_name ) ) #next_parent_name
              ed.save()
              query = self.queries_to_create_instance_tables(child, ed.id, parent_name, parent_table_name )
              next_query = next_query + query
          else: 
            if len(child.child_elements) > 0 :
                (q, f) = self._create_instance_tables_query_inner_loop(elementdef=child, parent_id=parent_id,  parent_name=formatted_join( next_parent_name, child.name ), parent_table_name=parent_table_name) #next-parent-name
            else:
                local_fields.append( self._db_field_definition_string(child) )
                (q,f) = self._create_instance_tables_query_inner_loop(elementdef=child, parent_id=parent_id, parent_name=next_parent_name, parent_table_name=parent_table_name ) #next-parent-name
            next_query = next_query + q
            local_fields = local_fields + f
      return (next_query, local_fields)

    def _db_field_definition_string(self, elementdef):
        """ generates the sql string to conform to the expected data type """
        label = self._hack_to_get_cchq_working( sanitize( elementdef.name ) )
        if elementdef.type == None:
            # This is an issue.  For now just log it as an error and default
            # it to a string
            logging.error("No data type found in element: %s! will use a string data type" % elementdef)
            elementdef.type = "string"
        if elementdef.type[0:5] == 'list.':
            field = ''
            simple_type = self.formdef.types[elementdef.type]
            if simple_type is not None:
                for value in simple_type.multiselect_values:
                    column_name = self._truncate(label + "_" + value)
                    column_type = self._get_db_type( 'boolean' )
                    field += "%s %s, " % (column_name, column_type)
            return field
        field = self._truncate(label) + " " + self._get_db_type( elementdef.type ) + ", "
        return field

    def _get_db_type(self, type):
        type = type.lower()
        if settings.DATABASE_ENGINE=='mysql' :
            if type in self.XSD_TO_MYSQL_TYPES: 
                return self.XSD_TO_MYSQL_TYPES[type]
            return self.XSD_TO_MYSQL_TYPES['default']
        else:
            if type in self.XSD_TO_DEFAULT_TYPES: 
                return self.XSD_TO_DEFAULT_TYPES[type]
            return self.XSD_TO_DEFAULT_TYPES['default']
        
    def _truncate(self, field_name):
        '''Truncates a field name to _MAX_FIELD_NAME_LENTH characters, which 
           is the max length allowed by mysql.  This is NOT smart enough to 
           check for conflicts, so there could be issues if an xform has two 
           very similar, very long, fields.'''
        # TODO: fix the above
        if len(field_name) > _MAX_FIELD_NAME_LENTH:
            return field_name[:_MAX_FIELD_NAME_LENTH]
        return field_name
    
    def _trim2chars(self, string):
        return string[0:len(string)-2]
        
class XFormDBTablePopulator(XFormProcessor):
    """ This class is responsible for parsing an xform instance 
    and populating the corresponding db tables dynamically
    
    If there are errors, these errors will be stored in self.errors
    """

    DB_NON_STRING_TYPES = (
        'integer',
        'int',
        'decimal',
        'double',
        'float',
        'datetime',
        'date',
        'time',
        'gyear',
        'gmonthday',
        'boolean',
        'base64binary',
        'hexbinary',
    )
    
    DB_NUMERIC_TYPES = {
        'integer': int, 'int': int, 'decimal': float, 'double' : float, 'float':float,'gyear':int        
    }
        
    def __init__(self, formdef, formdefmodel):
        self.formdef = formdef
        self.formdefmodel = formdefmodel
        self.errors = XFormErrors(formdef.target_namespace)
        
    def populate(self, data_tree):
        return self.queries_to_populate_instance_tables(data_tree=data_tree, 
                                                        elementdef=self.formdef.root, 
                                                        parent_name=self.formdef.name) 

        
    def queries_to_populate_instance_tables(self, data_tree, elementdef, parent_name='', parent_table_name='', parent_id=0):
      if data_tree is None and elementdef:
          self.errors.missing.append( "Missing element: %s" % elementdef.name )
          return
      
      table_name = get_registered_table_name( elementdef.xpath, self.formdef.target_namespace, self.formdef.version, domain=self.formdefmodel.domain)
      if len( parent_table_name ) > 0:
          # todo - make sure this is thread-safe (in case someone else is updating table). ;)
          # currently this assumes that we update child elements at exactly the same time we update parents =b
          cursor = connection.cursor()
          s = "SELECT id FROM " + str(parent_table_name) + " order by id DESC"
          logging.debug(s)
          cursor.execute(s)
          row = cursor.fetchone()
          if row is not None:
              parent_id = row[0]
          else:
              parent_id = 1
      
      query = self._populate_instance_tables_inner_loop(data_tree=data_tree, elementdef=elementdef, \
                                                        parent_name=parent_name, parent_table_name=table_name, \
                                                        parent_id=parent_id)
      query.parent_id = parent_id
      return query

    def _populate_instance_tables_inner_loop(self, data_tree, elementdef, parent_name='', \
                                             parent_table_name='', parent_id=0):
      if data_tree is None and elementdef:
          self.errors.missing.append( "Missing element: %s" % elementdef.name )
          return
      local_field_value_dict = {};
      next_query = Query(parent_table_name)
      if len(elementdef.child_elements)== 0:
          field_value_dict = {}
          if elementdef.is_repeatable :
              try:
                  field_value_dict = self._get_formatted_field_and_value(elementdef,data_tree.text)
              except TypeError, e:
                  self.errors.bad_type.append( unicode(e) )
          return Query( parent_table_name, field_value_dict )
      for def_child in elementdef.child_elements:
        data_node = None
        
        # todo - make sure this works in a case-insensitive way
        # find the data matching the current elementdef
        # todo - put in a check for root.isRepeatable
        next_parent_name = formatted_join(parent_name, elementdef.name)
        if def_child.is_repeatable :
            for data_child in case_insensitive_iter(data_tree, '{'+self.formdef.target_namespace+'}'+ self._data_name( elementdef.name, def_child.name) ):
                query = self.queries_to_populate_instance_tables(data_child, def_child, next_parent_name, \
                                                                 parent_table_name, parent_id)
                if next_query is not None:
                    next_query.child_queries = next_query.child_queries + [ query ]
                else:
                    next_query = query
        else:
            # if there are children (which are not repeatable) then flatten the table
            for data_child in case_insensitive_iter(data_tree, '{'+self.formdef.target_namespace+'}'+ self._data_name( elementdef.name, def_child.name) ):
                data_node = data_child
                break;
            if data_node is None:
                # no biggie - repeatable and irrelevant fields in the schema 
                # do not show up in the instance
                self.errors.missing.append( def_child.name )
                continue
            if( len(def_child.child_elements)>0 ):
                # here we are propagating, not onlyt the list of fields and values, but aso the child queries
                query = self._populate_instance_tables_inner_loop(data_tree=data_node, \
                                                                  elementdef=def_child, \
                                                                  parent_name=parent_name, \
                                                                  parent_table_name=parent_table_name)
                next_query.child_queries = next_query.child_queries + query.child_queries
                local_field_value_dict.update( query.field_value_dict )
            else:
                # if there are no children, then add values to the table
                if data_node.text is not None :
                    try:
                        field_value_dict = self._get_formatted_field_and_value(def_child, data_node.text)
                    except TypeError, e:
                        self.errors.bad_type.append( unicode(e) )
                    local_field_value_dict.update( field_value_dict )
                query = self._populate_instance_tables_inner_loop(data_node, def_child, \
                                                                  next_parent_name, parent_table_name)
                next_query.child_queries = next_query.child_queries + query.child_queries 
                local_field_value_dict.update( query.field_value_dict )
      q = Query( parent_table_name, local_field_value_dict )
      q.child_queries = q.child_queries + [ next_query ]
      return q
    
    def _get_formatted_field_and_value(self, elementdef, raw_value):
        """ returns a dictionary of key-value pairs """
        label = self._hack_to_get_cchq_working( sanitize(elementdef.name) )
        #don't sanitize value yet, since numbers/dates should not be sanitized in the same way
        if elementdef.type[0:5] == 'list.':
            field = ''
            value = ''
            values = raw_value.split()
            simple_type = self.formdef.types[elementdef.type]
            if simple_type is not None and simple_type.multiselect_values is not None:
                field_value = {}
                for v in values:
                    v = sanitize(v)
                    if v in simple_type.multiselect_values:
                        field_value.update( { label + "_" + v : '1' } )
                return field_value
        return { label : self._db_format(elementdef.type, raw_value) }

    def _db_format(self, type, text):
        if type is None:
            raise TypeError("No type found for value: %s." % text)
        type = type.lower()
        if text == '' or text is None:
            raise TypeError("No value provided for element: %s." % type)
        if type in self.DB_NON_STRING_TYPES:
            #dmyung :: some additional input validation
            if self.DB_NUMERIC_TYPES.has_key(type):
                typefunc = self.DB_NUMERIC_TYPES[type]
                try:
                    val = typefunc(text.strip())
                    return str(val)
                except:
                    raise TypeError("Error validating type %s with value %s (is not %s)" % \
                                    (type,text,str(typefunc)) )
            elif type == "datetime" :
                text = string.replace(text,'T',' ')
                if settings.DATABASE_ENGINE!='mysql' :
                    # truncate microseconds
                    index = text.rfind('.')
                    if index != -1:
                        text = text[0:index]
                return text.strip()
            else:
                return text.strip()
        else:
            return text.strip()

    def _data_name(self, parent_name, child_name):
        if child_name[0:len(parent_name)].lower() == parent_name.lower():
            child_name = child_name[len(parent_name)+1:len(child_name)]
        return child_name

class XFormErrors(Exception):
    '''Exception to make dealing with xform query errors easier.'''
   
    def __init__(self, xform_name=None):
        self.xform_name = xform_name
        self.missing = []
        self.bad_type = []
        # TODO - add checks for the following
        self.extra = [] # requires maintaining a data structure for input tree 
        self.duplicate = [] # requires something better than case_insensitive_iter()

    def __str__(self):
        return unicode(self).encode('utf-8')
        
    def __unicode__(self):
        error_msgs = []
        error_msgs.append("Missing fields: (%s)" % (",".join(self.missing)))
        error_msgs.append("Extra fields: (%s)" % (",".join(self.extra)))
        error_msgs.append("Duplicate fields: (%s)" % (",".join(self.duplicate)))
        error_msgs.append( "Poorly formatted fields: (%s)" % (",".join(self.bad_type)) )
        self.error_string = "\n".join(error_msgs)
        return "Error for instance of %s: \n%s" % (self.xform_name, self.error_string)
    
    def is_empty(self):
        return not( self.missing or self.extra or self.duplicate or self.bad_type )
    
    def str(self, field):
        if not hasattr(self, field.lower() ):
            return unicode(self)
        return "%s Error for instance of %s: \n%s" % \
               ( field, self.xform_name, ",".join(getattr(self,field.lower() )) )

def is_schema_registered(target_namespace, version=None):
    """ given a form and version is that form registered """
    try:
        fdd = FormDefModel.objects.get(target_namespace=target_namespace, version=version)
        return True
    except FormDefModel.DoesNotExist:
        return False

def get_registered_table_name(xpath, target_namespace, version=None, domain=None):
    """From an xpath, namespace and version, get a tablename"""
    fdd = FormDefModel.objects.get(target_namespace=target_namespace, version=version, domain=domain)
    return ElementDefModel.objects.get(xpath=xpath, form=fdd).table_name


def get_instance_data_handle_type():
    """Get the handling type used by the receiver that marks attachments
       as being processed by the xformmanager"""
    return SubmissionHandlingType.objects.get_or_create(app="xformmanager", method="instance_data")[0]

def get_deleted_handle_type():
    """Get the handling type used by the receiver that marks attachments
       as being processed by the xformmanager"""
    return SubmissionHandlingType.objects.get_or_create(app="xformmanager", method="deleted")[0]

def remove_metadata(meta):
    # support generically "unhandling" the attachments and then 
    # delete the actual metadata object
    meta.attachment.unhandled(get_instance_data_handle_type())
    meta.delete()

    