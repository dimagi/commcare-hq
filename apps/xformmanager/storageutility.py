""" Given an xform definition, storageutility generates dynamic data tables.
Given an xml instance, storeagutility populates the data tables.

Basically, storageutility abstracts away all interaction with the database,
and it only knows about the data structures in xformdef.py

"""

from django.db import connection, transaction, DatabaseError
from xformmanager.models import ElementDefModel, FormDefModel, Metadata
from xformmanager.xformdata import *
from xformmanager.util import *
from xformmanager.xformdef import FormDef
from datetime import datetime
from lxml import etree
import settings
import logging
import re
import os
import string

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
    
    META_FIELDS = ['meta_formname','meta_commcareversion','meta_formversion','meta_deviceid','meta_timestart','meta_timeend','meta_username','meta_chw_id','meta_uid']
    

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
        logging.debug("StorageProvider: saving form data")
        tree=etree.parse(data_stream_pointer)
        root=tree.getroot()
        self.formdef = formdef
        queries = self.queries_to_populate_instance_tables(data_tree=root, elementdef=formdef, parent_name=formdef.name )
        new_rawdata_id = queries.execute_insert()
        metadata_model = self._parse_meta_data( root )
        if metadata_model:
            metadata_model.formdefmodel = formdefmodel
            metadata_model.submission = submission
            metadata_model.raw_data = new_rawdata_id
            metadata_model.save()
            return True
        return False
        
    
    def save_form_data(self, xml_file_name, submission):
        f = open(xml_file_name, "r")
        # should match XMLNS
        xmlns = get_xmlns(f)
        if xmlns is None: 
            logging.error("NO XMLNS FOUND IN SUBMITTED FORM %s" % xml_file_name)
            return False
        formdef = FormDefModel.objects.all().filter(target_namespace=xmlns)
        
        if formdef is None or len(formdef) == 0:
            logging.error("XMLNS %s could not be matches to any registered formdef." % xmlns)
            return False
        # the above check is not sufficient
        if formdef[0].xsd_file_location is None:
            logging.error("Schema for form %s could not be found on the file system." % formdef[0].id)
            return False
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
        fdd.save()

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
            for data_child in self._case_insensitive_iter(data_tree, '{'+self.formdef.target_namespace+'}'+ self._data_name( elementdef.name, def_child.name) ):
                query = self.queries_to_populate_instance_tables(data_child, def_child, next_parent_name, parent_table_name, parent_id )
                if next_query is not None:
                    next_query.child_queries = next_query.child_queries + [ query ]
                else:
                    next_query = query
        else:
            # if there are children (which are not repeatable) then flatten the table
            for data_child in self._case_insensitive_iter(data_tree, '{'+self.formdef.target_namespace+'}'+ self._data_name( elementdef.name, def_child.name) ):
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
    def remove_instance_matching_schema(self, formdef_id, instance_id):
        fdm = FormDefModel.objects.get(pk=formdef_id)
        edm_id = fdm.element.id
        edm = ElementDefModel.objects.get(pk=edm_id)
        cursor = connection.cursor()
        cursor.execute( \
            " delete from " + edm.table_name + " where id = %s ", [instance_id] )
        try:
            Metadata.objects.get(raw_data=instance_id, formdefmodel=formdef_id).delete()
        except Metadata.DoesNotExist:
            # not a problem since this simply means the data was 
            # never successfully registered
            return
    
    """ This is commented out for now because I suspect there's a bug in it which
    may cause us to delete valuable data tables by accident
    The vast majority of cases won't have nested tables, so keeping the nested
    data around doesn't eat up that much space. TODO - fix and test rigorously
    
    @transaction.commit_on_success
    def remove_instance_matching_schema(self, formdef_id, instance_id):
        fdm = FormDefModel.objects.get(pk=formdef_id)
        edm_id = fdm.ElementDefModel.id
        edm = ElementDefModel.objects.get(pk=edm_id)
        _remove_instance_inner_loop(edm.id, instance_id)

    def _remove_instance_inner_loop(self, elementdef_id, instance_id):
        edms = ElementDefModel.objects.filter(parent_id=elementdef_id)
        for edm in edms:
            rows = cursor.execute( " select id, parent_id from " + edm.table_name + \
                                   " where parent_id = %s ", [instance_id] )
            if rows:
                for row in rows:
                    _remove_instance_inner_loop( row['id'] )
                    cursor.execute( " delete from " + edm.table_name + \
                                   " where parent_id = %s ", [instance_id] )
        edm = ElementDefModel.objects.get(id=elementdef_id)
        cursor.execute( " delete from " + edm.table_name + " where id = %s ", [instance_id] )
    """

    @transaction.commit_on_success
    def remove_schema(self, id, delete_xml=True):
        fdds = FormDefModel.objects.all().filter(id=id) 
        if fdds is None or len(fdds) == 0:
            logging.error("  Schema with id %s could not be found. Not deleted." % id)
            return    
        # must remove tables first since removing form_meta automatically deletes some tables
        self._remove_form_tables(fdds[0])
        self._remove_form_models(fdds[0], delete_xml)
        meta = Metadata.objects.all().filter(formdefmodel=fdds[0]).delete()
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
        if text == '':
            logging.error("No xml input provided!")
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
            so as not to break dan's code (reporting/graphing). Should fix dan's code t use metadata tables now.
            
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
        
    def _parse_meta_data(self, data_tree):
        m = Metadata()
        meta_tree = None
        
        if data_tree is None:
            self._error("Submitted form is empty!")
            return m
        # find meta node
        for data_child in self._case_insensitive_iter(data_tree, '{'+self.formdef.target_namespace+'}'+ "Meta" ):
            meta_tree = data_child
            break;
        if meta_tree is None:
            self._info("xformmanager: storageutility - no metadata found for %s" % \
                       (self.formdef.target_namespace) )
            return m
        
        # parse the meta data (children of meta node)
        for element in meta_tree:
            # element.tag is for example <FormName>
            # todo: this comparison should be made much less brittle - replace with a comparator object?
            tag = self._strip_namespace( element.tag ).lower()
            if tag in Metadata.fields:
                # must find out the type of an element field
                value = self._format_field(m,tag,element.text)
                # the following line means "model.tag = value"
                setattr( m,tag,value )
            else:
                self._info( ("Metadata %s is nonstandard. Not saved." % (tag)) )
        return m
        
    # can flesh this out or integrate with other functions later
    def _format_field(self, model, name, value):
        """ should handle any sort of conversion for 'meta' field values """
        t = type( getattr(model,name) )
        if t == datetime:
            return value.replace('T',' ')
        return value
        
    def _strip_namespace(self, tag):
        i = tag.find('}')
        tag = tag[i+1:len(tag)]
        return tag

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
            fdd.delete()
            Metadata.objects.filter(formdefmodel=fdd).delete()
            
                        
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
        
        
    def _case_insensitive_iter(self, data_tree, tag):
        if tag == "*":
            tag = None
        if tag is None or data_tree.tag.lower() == tag.lower():
            yield data_tree
        for d in data_tree: 
            for e in self._case_insensitive_iter(d,tag):
                yield e 

    def _data_name(self, parent_name, child_name):
        if child_name[0:len(parent_name)].lower() == parent_name.lower():
            child_name = child_name[len(parent_name)+1:len(child_name)]
        return child_name

    def _info(self, string):
        """ Currently this is only used to log extra metadata - no biggie. """
        logging.info(string)
        
    def _error(self, string):
        """ all parsing oddness gets logged here For now, we log and return.
        We could also just throw an exception here...
        
        """
        logging.error(string)

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
        
