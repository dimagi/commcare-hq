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

# TODO: sanitize all inputs to avoid database keywords
# e.g. no 'where' columns, etc.

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
        self.formdef = self.__strip_meta_def( formdef )
        queries = self.queries_to_create_instance_tables( formdef, '', formdef.name, formdef.name)
        self.__execute_queries(queries)
        return fdd
   	
    @transaction.commit_on_success
    def save_form_data_matching_formdef(self, data_stream_pointer, formdef):
        logging.debug("StorageProvider: saving form data")
        skip_junk(data_stream_pointer)
        tree = etree.parse(data_stream_pointer)
        root = tree.getroot()
        self.formdef = formdef
        self.__parse_meta_data( root )
        queries = self.queries_to_populate_instance_tables(data_tree=root, elementdef=formdef, parent_name=formdef.name )
        queries.execute_insert()
        
    def save_form_data(self, xml_file_name):
        logging.debug("Getting data from xml file at " + xml_file_name)
        f = open(xml_file_name, "r")
        xsd_form_name = get_xmlns(f)
        if xsd_form_name is None: return
        logging.debug("Form name is " + xsd_form_name)
        xsd = FormDefModel.objects.all().filter(form_name=xsd_form_name)
        
        if xsd is None or len(xsd) == 0:
            logging.error("NO XMLNS FOUND IN SUBMITTED FORM")
            return
        # the above check is not sufficient
        if xsd[0].xsd_file_location is None:
            logging.error("THIS INSTANCE DATA DOES NOT MATCH ANY REGISTERED SCHEMAS")
            return
        logging.debug("Schema is located at " + xsd[0].xsd_file_location)
        g = open( xsd[0].xsd_file_location ,"r")
        formdef = self.__strip_meta_def( FormDef(g) )
        g.close()
        
        logging.debug("Saving form data with known xsd")
        f.seek(0,0)
        self.save_form_data_matching_formdef(f, formdef)
        f.close()
        logging.debug("Form data successfully saved")
        return xsd_form_name

    def update_models(self, formdef):
        """ save element metadata """
        fdd = FormDefModel()
        fdd.name = str(formdef.name)
        #todo: fix this so we don't have to parse table twice
        fdd.form_name = get_table_name(formdef.target_namespace)
        fdd.target_namespace = formdef.target_namespace
        fdd.save()

        ed = ElementDefModel()
        ed.name=str(fdd.name)
        ed.table_name=get_table_name(formdef.target_namespace)
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
        table_name = get_table_name( formatted_join(parent_name, elementdef.name) )
        
        (next_query, fields) = self.__create_instance_tables_query_inner_loop(elementdef, parent_id, parent_name, parent_table_name )
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
        if parent_id is not '':
            if settings.DATABASE_ENGINE=='mysql' :
                queries = queries + " parent_id INT(11), "
                queries = queries + " FOREIGN KEY (parent_id) REFERENCES " + get_table_name(parent_table_name) + "(id) ON DELETE SET NULL"
            else:
                queries = queries + " parent_id REFERENCES " + get_table_name(parent_table_name) + "(id) ON DELETE SET NULL"
        else:
            queries = self.__trim2chars(queries)
        queries = queries + " );"
        queries = queries + next_query;
        return queries
    
    def __create_instance_tables_query_inner_loop(self, elementdef, parent_id, parent_name='', parent_table_name=''):
      """ This is 'handle' instead of 'create'(_children_tables) because not only are we 
      creating children tables, we are also gathering/passing children/field information back to the parent.
      """
      
      if not elementdef: return
      local_fields = [];
      
      next_query = ''
      if elementdef.is_repeatable and len(elementdef.child_elements)== 0 :
          return (next_query, self.__db_field_name(elementdef) )
      for child in elementdef.child_elements:
          # put in a check for root.isRepeatable
          next_parent_name = formatted_join(parent_name, elementdef.name)
          if child.is_repeatable :
              # repeatable elements must generate a new table
              if parent_id == '':
                  ed = ElementDefModel(name=str(child.name), form_id=self.formdata.id,
                                  table_name = get_table_name( formatted_join(next_parent_name, child.name) ) ) #next_parent_name
                  ed.save()
                  ed.parent = ed
              else:
                  ed = ElementDefModel(name=str(child.name), parent_id=parent_id, form=self.formdata,
                                  table_name = get_table_name( formatted_join(next_parent_name, child.name) ) ) #next_parent_name
              ed.save()
              next_query = self.queries_to_create_instance_tables(child, ed.id, parent_name, parent_table_name )
          else: 
            if len(child.child_elements) > 0 :
                (q, f) = self.__create_instance_tables_query_inner_loop(elementdef=child, parent_id=parent_id,  parent_name=formatted_join( next_parent_name, child.name ), parent_table_name=parent_table_name ) #next-parent-name
            else:
                local_fields.append( self.__db_field_name(child) )
                (q,f) = self.__create_instance_tables_query_inner_loop(elementdef=child, parent_id=parent_id, parent_name=next_parent_name, parent_table_name=parent_table_name ) #next-parent-name
            next_query = next_query + q
            local_fields = local_fields + f
      return (next_query, local_fields)
    
    def queries_to_populate_instance_tables(self, data_tree, elementdef, parent_name='', parent_table_name='', parent_id=0 ):
      if data_tree is None : return
      if not elementdef: return
      
      table_name = get_table_name( formatted_join(parent_name, elementdef.name) )      
      if len( parent_table_name ) > 0:          
          # todo - make sure this is thread-safe (in case someone else is updating table). ;)
          # currently this assumes that we update child elements at exactly the same time we update parents =b
          cursor = connection.cursor()
          s = "SELECT id FROM " + str(parent_table_name)
          logging.debug(s)
          cursor.execute(s)
          row = cursor.fetchone()
          if row is not None:
              parent_id = row[0]
          else:
              parent_id = 1
      
      query = self.__populate_instance_tables_inner_loop(data_tree=data_tree, elementdef=elementdef, parent_name=parent_name, parent_table_name=table_name, parent_id=parent_id )
      query.parent_id = parent_id
      return query

    def __populate_instance_tables_inner_loop(self, data_tree, elementdef, parent_name='', parent_table_name='', parent_id=0 ):
      if data_tree is None: return
      if not elementdef : return
      local_field_value_dict = {};
      
      next_query = Query(parent_table_name)
      if len(elementdef.child_elements)== 0:
          field_value_dict = {}
          if elementdef.is_repeatable :
              field_value_dict = self.__get_formatted_fields_and_values(elementdef,data_tree.text)
          return Query( parent_table_name, field_value_dict )
      for def_child in elementdef.child_elements:        
        data_node = None
        
        # todo - make sure this works in a case-insensitive way
        # find the data matching the current elementdef
        # todo - put in a check for root.isRepeatable
        next_parent_name = formatted_join(parent_name, elementdef.name)
        if def_child.is_repeatable :
            for data_child in self.__case_insensitive_iter(data_tree, '{'+self.formdef.target_namespace+'}'+ self.__data_name( elementdef.name, def_child.name) ):
                query = self.queries_to_populate_instance_tables(data_child, def_child, next_parent_name, parent_table_name, parent_id )
                if next_query is not None:
                    next_query.child_queries = next_query.child_queries + [ query ]
                else:
                    next_query = query
        else:
            # if there are children (which are not repeatable) then flatten the table
            for data_child in self.__case_insensitive_iter(data_tree, '{'+self.formdef.target_namespace+'}'+ self.__data_name( elementdef.name, def_child.name) ):
                data_node = data_child
                break;
            if data_node is None:
                logging.debug("xformmanager: storageutility - no values parsed for " + '{'+self.formdef.target_namespace+'}' + def_child.name)
                continue
            if( len(def_child.child_elements)>0 ):
                if data_node is not None:
                    # here we are propagating, not onlyt the list of fields and values, but aso the child queries
                    query = self.__populate_instance_tables_inner_loop(data_tree=data_node, elementdef=def_child, parent_name=parent_name, parent_table_name=parent_table_name )
                    next_query.child_queries = next_query.child_queries + query.child_queries
                    local_field_value_dict.update( query.field_value_dict )
            else:
                # if there are no children, then add values to the table
                if data_node.text is not None :
                    field_value_dict = self.__get_formatted_fields_and_values(def_child, data_node.text)
                    local_field_value_dict.update( field_value_dict )
                query = self.__populate_instance_tables_inner_loop(data_node, def_child, next_parent_name, parent_table_name)
                next_query.child_queries = next_query.child_queries + query.child_queries 
                local_field_value_dict.update( query.field_value_dict )
      query = Query(parent_table_name, local_field_value_dict )
      query.child_queries = query.child_queries + [ next_query ]
      return query

    def __trim2chars(self, string):
        return string[0:len(string)-2]
        
    def __get_db_type(self, type):
        type = type.lower()
        if settings.DATABASE_ENGINE=='mysql' :
            if type in self.XSD_TO_MYSQL_TYPES: 
                return self.XSD_TO_MYSQL_TYPES[type]
            return self.XSD_TO_MYSQL_TYPES['default']
        else:
            if type in self.XSD_TO_DEFAULT_TYPES: 
                return self.XSD_TO_DEFAULT_TYPES[type]
            return self.XSD_TO_DEFAULT_TYPES['default']

        
        
    def __db_format(self, type, text):
        type = type.lower()
        if text == '':
            logging.error("Poorly formatted xml input!")
            return ''
        if type in self.DB_NON_STRING_TYPES:
            #dmyung :: some additional input validation
            if self.DB_NUMERIC_TYPES.has_key(type):
                typefunc = self.DB_NUMERIC_TYPES[type]
                try:
                    val = typefunc(text.strip())
                    return str(val)
                except:
                    logging.error("Error validating type %s with value %s, object is not a %s" % (type,text,str(typefunc)))
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



    def __hack_to_get_cchq_working(self, name):
                
        prefix = sanitize (self.formdef.name) + "_"
        
        if name[0:len(prefix)] == prefix:
            name = name[len(prefix)+1:len(name)]
        splits = name.split('_')
        endsplit = splits[-2:]
        if self.META_FIELDS.count('_'.join(endsplit)) == 1:
            return '_'.join(endsplit)
        return name

    def __db_field_name(self, elementdef):
        label = self.__hack_to_get_cchq_working( sanitize( elementdef.name ) )
        if elementdef.type[0:5] == 'list.':
            field = ''
            simple_type = self.formdef.types[elementdef.type]
            if simple_type is not None:
                for values in simple_type.multiselect_values:
                    field = field + label + "_" + values + " " + self.__get_db_type( 'boolean' ) + ", " 
            return field
        return  label + " " + self.__get_db_type( elementdef.type ) + ", "

    def __get_formatted_fields_and_values(self, elementdef, raw_value):
        """ returns a dictionary of key-value pairs """
        label = self.__hack_to_get_cchq_working( sanitize(elementdef.name) )
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
        return { label : self.__db_format(elementdef.type, raw_value) }

    def __execute_queries(self, queries):
        # todo - rollback on fail
        if queries is None or len(queries) == 0:
            logging.error("xformmanager: storageutility - xform " + self.formdef.target_namespace + " could not be parsed")
            return
        logging.debug(queries)
        cursor = connection.cursor()
        if settings.DATABASE_ENGINE=='mysql' :
            cursor.execute(queries)            
        else:
            simple_queries = queries.split(';')
            for query in simple_queries: 
                cursor.execute(query)

    @transaction.commit_on_success
    def remove_schema(self, id):
        fdds = FormDefModel.objects.all().filter(id=id) 
        if fdds is None or len(fdds) == 0:
            logging.error("  Schema " + name + " could not be found. Not deleted.")
            return    
        # must remove tables first since removing form_meta automatically deletes some tables
        self.__remove_form_tables(fdds[0])
        self.__remove_form_meta(fdds[0])
        # when we delete formdefdata, django automatically deletes all associated elementdefdata
    
    # make sure when calling this function always to confirm with the user
    def clear(self):
        """ removes all schemas found in XSD_REPOSITORY_PATH
            and associated tables. It also deletes the contents of XFORM_SUBMISSION_PATH.        
        """
        self.__remove_form_tables()
        self.__remove_form_meta()
        # when we delete formdefdata, django automatically deletes all associated elementdefdata
            
        # drop all xml data instance files stored in XFORM_SUBMISSION_PATH
        for file in os.listdir( settings.rapidsms_apps_conf['receiver']['xform_submission_path'] ):
            file = os.path.join( settings.rapidsms_apps_conf['receiver']['xform_submission_path'] , file)
            logging.debug(  "Deleting " + file )
            stat = os.stat(file)
            if S_ISREG(stat[ST_MODE]) and os.access(file, os.W_OK):
                os.remove( file )
            else:
                logging.debug(  "  WARNING: Permission denied to access " + file )
                continue
    
    #TODO: commcare-specific functionality - should pull out into separate file
    def __strip_meta_def(self, formdef):
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
                        field = self.__data_name(meta_node.name,element.name)
                        if field.lower() not in Metadata.fields:
                            new_meta_children = new_meta_children + [ element ]
                    if len(new_meta_children) > 0:
                        meta_node.child_elements = new_meta_children
        """
        return formdef
        
    def __parse_meta_data(self, data_tree):
        if data_tree is None: return
        meta_tree = None
        # find meta node
        for data_child in self.__case_insensitive_iter(data_tree, '{'+self.formdef.target_namespace+'}'+ "Meta" ):
            meta_tree = data_child
            break;
        if meta_tree is None:
            logging.debug("xformmanager: storageutility - no metadata found for " + self.formdef.target_namespace)
            return
        
        m = Metadata()
        # parse the meta data (children of meta node)
        for element in meta_tree:
            # element.tag is for example <FormName>
            # todo: this comparison should be made much less brittle - replace with a comparator object?
            tag = self.__strip_namespace( element.tag ).lower()
            if tag in Metadata.fields:
                # must find out the type of an element field
                value = self.__format_field(m,tag,element.text)
                # the following line means "model.tag = value"
                setattr( m,tag,value )
        m.save()
        
    # can flesh this out or integrate with other functions later
    def __format_field(self, model, name, value):
        """ should handle any sort of conversion for 'meta' field values """
        t = type( getattr(model,name) )
        if t == datetime:
            return value.replace('T',' ')
        return value
        
    def __strip_namespace(self, tag):
        i = tag.find('}')
        tag = tag[i+1:len(tag)]
        return tag

    def __remove_form_meta(self,form=''):
        # drop all schemas, associated tables, and files
        if form == '':
            fdds = FormDefModel.objects.all().filter()
        else:
            fdds = FormDefModel.objects.all().filter(target_namespace=form.target_namespace)            
        for fdd in fdds:
            file = fdd.xsd_file_location
            if file is not None:
                logging.debug(  "  removing file " + file )
                os.remove(file)
            logging.debug(  "  deleting form definition for " + fdd.target_namespace )
            fdd.delete()
                        
    # in theory, there should be away to *not* remove elemenetdefdata when deleting formdef
    # until we figure out how to do that, this'll work fine
    def __remove_form_tables(self,form=''):
        # drop all element definitions and associated tables
        # the reverse ordering is a horrible hack (but efficient) 
        # to make sure we delete children before parents
        if form == '':
            edds = ElementDefModel.objects.all().filter().order_by("-table_name")
        else:
            edds = ElementDefModel.objects.all().filter(form=form).order_by("-table_name")
        for edd in edds:
            logging.debug(  "  deleting data table:" + edd.table_name )
            cursor = connection.cursor()
            cursor.execute("drop table " + edd.table_name)


    def __case_insensitive_iter(self, data_tree, tag):
        if tag == "*":
            tag = None
        if tag is None or data_tree.tag.lower() == tag.lower():
            yield data_tree
        for e in data_tree: 
            for e in self.__case_insensitive_iter(e,tag):
                yield e 

    def __data_name(self, parent_name, child_name):
        if child_name[0:len(parent_name)].lower() == parent_name.lower():
            child_name = child_name[len(parent_name)+1:len(child_name)]
        return child_name

class Query(object):
    """ stores all the information needed to run a query """
    
    def __init__(self, table_name='', field_value_dict={}, child_queries=[]): 
        self.table_name = table_name # string
        self.field_value_dict = field_value_dict # list of strings
        self.child_queries = child_queries # list of Queries
        self.parent_id = 0
        
    def execute_insert(self):
        if len( self.field_value_dict ) > 0:
            query_string = "INSERT INTO " + self.table_name + " (";
    
            for field in self.field_value_dict:
                query_string = query_string + field + ", "
            query_string = self.__trim2chars( query_string )
            if self.parent_id > 0: query_string = query_string + ", parent_id"
    
            query_string = query_string + ") VALUES( "

	    # we use c-style substitution to enable django-built in sql-injection protection
            for value in self.field_value_dict:
                query_string = query_string + "%s, "
            query_string = self.__trim2chars( query_string )
            if self.parent_id > 0: query_string = query_string + ", " + str(self.parent_id)
            query_string = query_string +  ");"

            values = []
            for value in self.field_value_dict:
                values = values + [ self.field_value_dict[ value ] ]
                
            self.__execute(query_string, values)
        
        for child_query in self.child_queries:
            child_query.execute_insert()
        
    def __execute(self, queries, values):
        # todo - rollback on fail
        if queries is None or len(queries) == 0:
            logging.error("xformmanager: storageutility - xform " + self.formdef.target_namespace + " could not be parsed")
            return
        cursor = connection.cursor()
        cursor.execute(queries, values)
        """ if settings.DATABASE_ENGINE=='mysql' 
            cursor.execute(queries)            
        else:
            simple_queries = queries.split(';')
            for query in simple_queries: 
                cursor.execute(query)
        """
        
    def __trim2chars(self, string):
        return string[0:len(string)-2]
        
