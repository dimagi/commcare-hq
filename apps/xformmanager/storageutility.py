""" Given an xform definition, storageutility generates dynamic data tables.
Given an xml instance, storeagutility populates the data tables.

Basically, storageutility abstracts away all interaction with the database,
and it only knows about the data structures in xformdef.py

"""

import re
import os
import logging
import settings
import string
from datetime import datetime, timedelta

from lxml import etree
from MySQLdb import IntegrityError
from django.db import connection, transaction, DatabaseError

from xformmanager.models import ElementDefModel, FormDefModel, Metadata
from xformmanager.util import *
from xformmanager.xformdef import FormDef
from receiver.models import SubmissionHandlingOccurrence, SubmissionHandlingType

from stat import S_ISREG, ST_MODE
import sys

_MAX_FIELD_NAME_LENTH = 64

class StorageUtility(object):
    """ This class handles everything that touches the database - both form and instance data."""
    # should pull this out into a rsc file...
    
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
    
    META_FIELDS = ['meta_formname','meta_commcareversion','meta_formversion','meta_deviceid',
                   'meta_timestart','meta_timeend','meta_username','meta_chw_id','meta_uid']
    
    def __init__(self):
        self.formdef = ''
        self.formdata = None
    
    @classmethod
    def get_meta_validation_errors(cls, element):
        '''Validates an ElementDef, assuming it is a meta block.  Ensures
           that every field we expect to find in the meta is there, and 
           that there are no extra fields.  Returns a dictionary of
           of any errors/warnings found in the following format:
           { "missing" : [list, of, missing, expected, fields]
             "duplicate" : [list, of, duplicate, fields]
             "extra" : [list, of, unexpected, fields]
           }
           If any of these lists are empty they won't be in the dictionary,
           and therefore if all are empty this method will return an empty
           dictionary.
        '''
        missing_fields = []
        extra_fields = []
        duplicate_fields = []
        found_fields = []
        missing_fields.extend(Metadata.fields)
        for field in element.child_elements:
            field_name = field.short_name.lower()
            if field_name in missing_fields:
                missing_fields.remove(field_name)
                found_fields.append(field_name)
            elif field_name in found_fields:
                # it was already found, therefore it must be 
                # a duplicate
                duplicate_fields.append(field_name)
            else:
                # it wasn't in the expected list, and wasn't a 
                # dupe, it must be an extra
                extra_fields.append(field_name)
        to_return = {}
        if missing_fields:
            to_return["missing"] = missing_fields
        if duplicate_fields:
            to_return["duplicate"] = duplicate_fields
        if extra_fields:
            to_return["extra"] = extra_fields
        return to_return
            
        
    @transaction.commit_on_success
    def add_schema(self, formdef):
        fdd = self.update_models(formdef)
        self.formdata = fdd
        self.formdef = self._strip_meta_def( formdef )
        queries = self.queries_to_create_instance_tables( formdef, fdd.element.id, formdef.name, formdef.name)
        self._execute_queries(queries)
        return fdd
   	
    @transaction.commit_on_success
    def save_form_data_matching_formdef(self, data_stream_pointer, formdef, formdefmodel, submission):
        """ returns True on success """
        logging.debug("StorageProvider: saving form data")
        tree=etree.parse(data_stream_pointer)
        root=tree.getroot()
        self.formdef = formdef
        queries = self.queries_to_populate_instance_tables(data_tree=root, elementdef=formdef, parent_name=formdef.name )
        new_rawdata_id = queries.execute_insert()
        metadata_model = Metadata()
        metadata_model.init( root, self.formdef.target_namespace )
        metadata_model.formdefmodel = formdefmodel
        metadata_model.submission = submission
        metadata_model.raw_data = new_rawdata_id
        metadata_model.save(self.formdef.target_namespace)
        # rl - seems like a strange place to put this message...
        # respond with the number of submissions they have
        # made today.
        startdate = datetime.now().date() 
        enddate = startdate + timedelta(days=1)
        message = metadata_model.get_submission_count(startdate, enddate)
        # TODO - fix meta.submission to point to real submission
        self._add_handled(metadata_model.submission, message)
        return True
    
    def save_form_data(self, xml_file_name, submission):
        """ returns True on success and false on fail """
        f = open(xml_file_name, "r")
        # should match XMLNS
        xmlns = self._get_xmlns(f)
        formdef = FormDefModel.objects.all().filter(target_namespace=xmlns)
        
        if formdef is None or len(formdef) == 0:
            raise self.XFormError("XMLNS %s could not be matched to any registered formdef." % xmlns)
        if formdef[0].xsd_file_location is None:
            raise self.XFormError("Schema for form %s could not be found on the file system." % formdef[0].id)
        g = open( formdef[0].xsd_file_location ,"r")
        stripped_formdef = self._strip_meta_def( FormDef(g) )
        g.close()
        
        f.seek(0,0)
        status = self.save_form_data_matching_formdef(f, stripped_formdef, formdef[0], submission)
        f.close()
        logging.debug("Schema %s successfully registered" % xmlns)
        return status

    def update_models(self, formdef):
        """ save element metadata """
        fdd = FormDefModel()
        fdd.name = str(formdef.name)
        #todo: fix this so we don't have to parse table twice
        fdd.form_name = create_table_name(formdef.target_namespace)
        fdd.target_namespace = formdef.target_namespace

        try:
            fdd.save()
        except IntegrityError, e:
            raise IntegrityError( ("Schema %s already exists." % fdd.target_namespace ) + \
                                   " Did you remember to update your version number?")
        ed = ElementDefModel()
        ed.name=str(fdd.name)
        ed.table_name=create_table_name(formdef.target_namespace)
        #ed.form_id = fdd.id
        ed.form = fdd
        ed.save()
        ed.parent = ed
        ed.save()
        
        fdd.element = ed
        fdd.save()
        
        # kind of odd that this is created but not saved here... 
        # not sure how to work around that, given required fields?
        return fdd
    
    # TODO - this should be cleaned up to use the same Query object that populate_instance_tables uses
    # (rather than just passing around tuples of strings)
    def queries_to_create_instance_tables(self, elementdef, parent_id, parent_name='', parent_table_name='' ):
        table_name = create_table_name( formatted_join(parent_name, elementdef.name) )
        
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
                queries = queries + " FOREIGN KEY (parent_id) REFERENCES " + create_table_name(parent_table_name) + "(id) ON DELETE SET NULL"
            else:
                queries = queries + " parent_id REFERENCES " + create_table_name(parent_table_name) + "(id) ON DELETE SET NULL"
        else:
            queries = self._trim2chars(queries)
        queries = queries + " );"
        queries = queries + next_query;
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
                  ed = ElementDefModel(name=str(child.name), form_id=self.formdata.id,
                       table_name = create_table_name( formatted_join(parent_name, child.name) ) ) #should parent_name be next_parent_name?
                  ed.save()
                  ed.parent = ed
              else:
                  ed = ElementDefModel(name=str(child.name), parent_id=parent_id, form=self.formdata,
                                  table_name = create_table_name( formatted_join(parent_name, child.name) ) ) #next_parent_name
              ed.save()
              next_query = self.queries_to_create_instance_tables(child, ed.id, parent_name, parent_table_name )
          else: 
            if len(child.child_elements) > 0 :
                (q, f) = self._create_instance_tables_query_inner_loop(elementdef=child, parent_id=parent_id,  parent_name=formatted_join( next_parent_name, child.name ), parent_table_name=parent_table_name ) #next-parent-name
            else:
                local_fields.append( self._db_field_definition_string(child) )
                (q,f) = self._create_instance_tables_query_inner_loop(elementdef=child, parent_id=parent_id, parent_name=next_parent_name, parent_table_name=parent_table_name ) #next-parent-name
            next_query = next_query + q
            local_fields = local_fields + f
      return (next_query, local_fields)
    
    def queries_to_populate_instance_tables(self, data_tree, elementdef, parent_name='', parent_table_name='', parent_id=0 ):
      if data_tree is None and not elementdef: return
      if data_tree is None and elementdef:
          # no biggie - repeatable and irrelevant fields in the schema 
          # do not show up in the instance
          return
      if data_tree is not None and not elementdef: 
          self._error("Unrecognized element: %s:%s" % \
                     (self.formdef.target_namespace, data_tree.tag) )
          return
      
      table_name = get_registered_table_name( formatted_join(parent_name, elementdef.name) )      
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
      
      query = self._populate_instance_tables_inner_loop(data_tree=data_tree, elementdef=elementdef, parent_name=parent_name, parent_table_name=table_name, parent_id=parent_id )
      query.parent_id = parent_id
      return query

    def _populate_instance_tables_inner_loop(self, data_tree, elementdef, parent_name='', parent_table_name='', parent_id=0 ):
      if data_tree is None and not elementdef: return
      if data_tree is None and elementdef:
          # no biggie - repeatable and irrelevant fields in the schema 
          # do not show up in the instance
          return
      if data_tree is not None and not elementdef: 
          self._error("Unrecognized element: %s:%s" % \
                     (self.formdef.target_namespace, data_tree.tag) )
          return
      
      local_field_value_dict = {};
      next_query = Query(parent_table_name)
      if len(elementdef.child_elements)== 0:
          field_value_dict = {}
          if elementdef.is_repeatable :
              field_value_dict = self._get_formatted_fields_and_values(elementdef,data_tree.text)
          return Query( parent_table_name, field_value_dict )
      for def_child in elementdef.child_elements:        
        data_node = None
        
        # todo - make sure this works in a case-insensitive way
        # find the data matching the current elementdef
        # todo - put in a check for root.isRepeatable
        next_parent_name = formatted_join(parent_name, elementdef.name)
        if def_child.is_repeatable :
            for data_child in case_insensitive_iter(data_tree, '{'+self.formdef.target_namespace+'}'+ self._data_name( elementdef.name, def_child.name) ):
                query = self.queries_to_populate_instance_tables(data_child, def_child, next_parent_name, parent_table_name, parent_id )
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
                continue
            if( len(def_child.child_elements)>0 ):
                # here we are propagating, not onlyt the list of fields and values, but aso the child queries
                query = self._populate_instance_tables_inner_loop(data_tree=data_node, elementdef=def_child, parent_name=parent_name, parent_table_name=parent_table_name )
                next_query.child_queries = next_query.child_queries + query.child_queries
                local_field_value_dict.update( query.field_value_dict )
            else:
                # if there are no children, then add values to the table
                if data_node.text is not None :
                    field_value_dict = self._get_formatted_fields_and_values(def_child, data_node.text)
                    local_field_value_dict.update( field_value_dict )
                query = self._populate_instance_tables_inner_loop(data_node, def_child, next_parent_name, parent_table_name)
                next_query.child_queries = next_query.child_queries + query.child_queries 
                local_field_value_dict.update( query.field_value_dict )
      query = Query(parent_table_name, local_field_value_dict )
      query.child_queries = query.child_queries + [ next_query ]
      return query

    # note that this does not remove the file from the filesystem 
    # (by design, for security)
    @transaction.commit_on_success
    def remove_instance_matching_schema(self, formdef_id, instance_id):
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
        # mark as intentionally handled
        # TODO - fix meta.submission to point to real submission
        self._add_handled_as_deleted(meta.submission)
        meta.delete()

    def _add_handled_as_deleted(self, attachment, message=''):
        '''Tells the receiver that this attachment's submission was handled.  
           Should only be called _after_ we are sure that we got a linked 
           schema of this type.
        '''
        try:
            handle_type = SubmissionHandlingType.objects.get(app="xformmanager", method="deleted")
        except SubmissionHandlingType.DoesNotExist:
            handle_type = SubmissionHandlingType.objects.create(app="xformmanager", method="deleted")
        # TODO - fix meta.submission to point to real submission
        attachment.handled(handle_type, message)

    def _add_handled(self, attachment, message):
        '''Tells the receiver that this attachment's submission was handled.  
           Should only be called _after_ we are sure that we got a linked 
           schema of this type.
        '''
        try:
            handle_type = SubmissionHandlingType.objects.get(app="xformmanager", method="instance_data")
        except SubmissionHandlingType.DoesNotExist:
            handle_type = SubmissionHandlingType.objects.create(app="xformmanager", method="instance_data")
        # TODO - fix meta.submission to point to real submission
        attachment.handled(handle_type, message)

    def _remove_handled(self, attachment):
        '''Tells the receiver that this attachment's submission was not handled.
           Only used when we are deleting data from xformmanager but not receiver
        '''
        try:
            handle_type = SubmissionHandlingType.objects.get(app="xformmanager", method="instance_data")
        except SubmissionHandlingType.DoesNotExist:
            handle_type = SubmissionHandlingType.objects.create(app="xformmanager", method="instance_data")
        # TODO - fix meta.submission to point to real submission
        attachment.unhandled(handle_type)

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
    def remove_schema(self, id, delete_xml=True):
        fdds = FormDefModel.objects.all().filter(id=id) 
        if fdds is None or len(fdds) == 0:
            logging.error("  Schema with id %s could not be found. Not deleted." % id)
            return    
        # must remove tables first since removing form_meta automatically deletes some tables
        self._remove_form_tables(fdds[0])
        self._remove_form_models(fdds[0], delete_xml)
        # when we delete formdefdata, django automatically deletes all associated elementdefdata
    
    # make sure when calling this function always to confirm with the user

    def clear(self, delete_xml=True):
        """ removes all schemas found in XSD_REPOSITORY_PATH
            and associated tables. 
            If delete_xml is true (default) it also deletes the 
            contents of XFORM_SUBMISSION_PATH.        
        """
        self._remove_form_tables()
        self._remove_form_models(delete_xml=delete_xml)
        # when we delete formdefdata, django automatically deletes all associated elementdefdata
            
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
    
    def _trim2chars(self, string):
        return string[0:len(string)-2]
        
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
        
    def _db_format(self, type, text):
        type = type.lower()
        if text == '' or text is None:
            logging.error("No xml input provided to _db_format!")
            return ''
        if type in self.DB_NON_STRING_TYPES:
            #dmyung :: some additional input validation
            if self.DB_NUMERIC_TYPES.has_key(type):
                typefunc = self.DB_NUMERIC_TYPES[type]
                try:
                    val = typefunc(text.strip())
                    return str(val)
                except:
                    self._error(\
                        "Error validating type %s with value %s (is not %s)" \
                        % (type,text,str(typefunc)))
                    return '0'
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



    def _hack_to_get_cchq_working(self, name):
                
        prefix = sanitize (self.formdef.name) + "_"
        
        if name[0:len(prefix)] == prefix:
            name = name[len(prefix)+1:len(name)]
        splits = name.split('_')
        endsplit = splits[-2:]
        if self.META_FIELDS.count('_'.join(endsplit)) == 1:
            return '_'.join(endsplit)
        
        return name

    def _db_field_definition_string(self, elementdef):
        """ generates the sql string to conform to the expected data type """
        label = self._hack_to_get_cchq_working( sanitize( elementdef.name ) )
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

    def _get_formatted_fields_and_values(self, elementdef, raw_value):
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
                    cursor.execute(query)
        else:
            cursor.execute(queries)            
    
    def _truncate(self, field_name):
        '''Truncates a field name to _MAX_FIELD_NAME_LENTH characters, which is the max length allowed
           by mysql.  This is NOT smart enough to check for conflicts, so there could
           be issues if an xform has two very similar, very long, fields'''
        if len(field_name) > _MAX_FIELD_NAME_LENTH:
            return field_name[:_MAX_FIELD_NAME_LENTH]
        return field_name
    
    #TODO: commcare-specific functionality - should pull out into separate file
    def _strip_meta_def(self, formdef):
        """ TODO: currently, we do not strip the duplicate meta information in the xformdata
            so as not to break dan's code (reporting/graphing). Should fix dan's code to
            use metadata tables now.
            
            root_node = formdef.child_elements[0]
            # this requires that 'meta' be the first child element within root node
            if len( root_node.child_elements ) > 0:
                meta_node = root_node.child_elements[0]
                new_meta_children = []
                if meta_node.name.lower().endswith('meta'):
                    # this rather tedious construction is so that we can support metadata with missing fields but not lose metadata with wrong fields
                    for element in meta_node.child_elements:
                        field = self._data_name(meta_node.name,element.name)
                        if field.lower() not in Metadata.fields:
                            new_meta_children = new_meta_children + [ element ]
                    if len(new_meta_children) > 0:
                        meta_node.child_elements = new_meta_children
        """
        return formdef
        
    def _remove_form_models(self,form='', delete_xml=True):
        """Drop all schemas, associated tables, and files"""
        if form == '':
            fdds = FormDefModel.objects.all().filter()
        else:
            fdds = FormDefModel.objects.all().filter(target_namespace=form.target_namespace)            
        for fdd in fdds:
            if delete_xml:
                file = fdd.xsd_file_location
                if file is not None:
                    logging.debug(  "  removing file " + file )
                    if os.path.exists(file):
                        os.remove(file)
                    else:
                        logging.warn("Tried to delete schema file: %s but it wasn't found!" % file)
            logging.debug(  "  deleting form definition for " + fdd.target_namespace )
            all_meta = Metadata.objects.filter(formdefmodel=fdd)
            for meta in all_meta:
                self._remove_handled(meta.submission)
            all_meta.delete()
            fdd.delete()
    
    # in theory, there should be away to *not* remove elemenetdefdata when deleting formdef
    # until we figure out how to do that, this'll work fine
    def _remove_form_tables(self,form=''):
        # drop all element definitions and associated tables
        # the reverse ordering is a horrible hack (but efficient) 
        # to make sure we delete children before parents
        if form == '':
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
        
    def _data_name(self, parent_name, child_name):
        if child_name[0:len(parent_name)].lower() == parent_name.lower():
            child_name = child_name[len(parent_name)+1:len(child_name)]
        return child_name

    def _error(self, string):
        """ all parsing oddness gets logged here For now, we log and return.
        We could also just throw an exception here...
        
        """
        logging.error(string)

    #temporary measure to get target form
    # todo - fix this to be more efficient, so we don't parse the file twice
    def _get_xmlns(self, stream):
        xml_string = get_xml_string(stream)
        try:
            root = etree.XML(xml_string)
        except etree.XMLSyntaxError:
            raise self.XFormError("XML Syntax Error")
        r = re.search('{[a-zA-Z0-9_\-\.\/\:]*}', root.tag)
        if r is None:
            raise self.XFormError("NO XMLNS FOUND IN SUBMITTED FORM")
        return r.group(0).strip('{').strip('}')

def get_registered_table_name(name):
    # this is purely for backwards compatibility
    for func in possible_naming_functions:
        table_name = func(name)
        if ElementDefModel.objects.filter(table_name=table_name):
            return table_name
    return None

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
    