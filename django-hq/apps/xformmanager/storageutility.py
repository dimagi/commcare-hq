from django.db import connection, transaction, DatabaseError
from xformmanager.models import ElementDefData, FormDefData
from xformmanager.xformdata import *
from xformmanager.util import *
from xformmanager.xformdef import FormDef
from lxml import etree
import settings
import logging
import re
import os

from stat import S_ISREG, ST_MODE
import sys

# TODO: sanitize all inputs to avoid database keywords
# e.g. no 'where' columns, etc.

class StorageUtility(object):
    """ This class handles everything that touches the database - both form and instance data."""
    # should pull this out into a rsc file...
    
    # Data types taken from mysql. 
    # This should really draw from django biult-in utilities which are database independent. 
    XSD_TO_DB_TYPES = {
        'string':'VARCHAR(255)',
        'integer':'INT(11)',
        'int':'INT(11)',
        'decimal':'DECIMAL(5,2)',
        'double':'DOUBLE',
        'float':'DOUBLE',
        'dateTime':'DATETIME', # string
        'date':'INT(11)', # string
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

    DB_NON_STRING_TYPES = (
        'integer',
        'int',
        'decimal',
        'double',
        'float'
        'dateTime',
        'date',
        'time'
        'gyear',
        'gmonthday',
        'boolean'
        'base64binary',
        'hexbinary',
    )
    
    DB_NUMERIC_TYPES = {
        'integer': int, 'int': int, 'decimal': float, 'double' : float, 'float':float,'gyear':int        
    }
    

    def add_schema(self, formdef):
        fdd = self.update_meta(formdef)
        self.form = fdd
        queries = self.queries_to_create_instance_tables( formdef, '', formdef.name, formdef.name)
        self.__execute_queries(queries)
        return fdd
    
    def save_form_data_matching_formdef(self, data_stream_pointer, formdef):
        logging.debug("StorageProvider: saving form data")
        skip_junk(data_stream_pointer)
        tree = etree.parse(data_stream_pointer)
        root = tree.getroot()
        self.namespace = formdef.target_namespace
        queries = self.queries_to_populate_instance_tables(data_tree=root, elementdef=formdef, parent_name=formdef.name )
        self.__execute_queries(queries)
        #I don't know why we need this.... but if we don't, unit tests break
        transaction.commit_unless_managed()

    def save_form_data(self, xml_file_name):
        logging.debug("Getting data from xml file at " + xml_file_name)
        f = open(xml_file_name, "r")
        xsd_form_name = get_xmlns(f)
        if xsd_form_name is None: return
        logging.debug("Form name is " + xsd_form_name)
        xsd = FormDefData.objects.all().filter(form_name=xsd_form_name)
        
        if xsd is None or len(xsd) == 0:
            logging.error("NO XMLNS FOUND IN SUBMITTED FORM")
            return
        logging.debug("Schema is located at " + xsd[0].xsd_file_location)
        g = open( xsd[0].xsd_file_location ,"r")
        formdef = FormDef(g)
        g.close()
        
        logging.debug("Saving form data with known xsd")
        f.seek(0,0)
        self.save_form_data_matching_formdef(f, formdef)
        f.close()
        logging.debug("Form data successfully saved")
        return xsd_form_name

    def update_meta(self, formdef):
        """ save element metadata """
        fdd = FormDefData()
        fdd.name = str(formdef.name)
        fdd.form_name = get_table_name(formdef.target_namespace)
        fdd.target_namespace = formdef.target_namespace
        fdd.save()

        ed = ElementDefData()
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

    def queries_to_create_instance_tables(self, elementdef, parent_id, parent_name='', parent_table_name='' ):
        table_name = get_table_name( self.__name(parent_name, elementdef.name) )
        
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
          next_parent_name = self.__name(parent_name, elementdef.name)
          if child.is_repeatable :
              # repeatable elements must generate a new table
              if parent_id == '':
                  ed = ElementDefData(name=str(child.name), form_id=self.form.id,
                                  table_name = get_table_name( self.__name(next_parent_name, child.name) ) ) #next_parent_name
                  ed.save()
                  ed.parent = ed
              else:
                  ed = ElementDefData(name=str(child.name), parent_id=parent_id, form=self.form,
                                  table_name = get_table_name( self.__name(next_parent_name, child.name) ) ) #next_parent_name
              ed.save()
              next_query = self.queries_to_create_instance_tables(child, ed.id, parent_name, parent_table_name )
          else: 
            if len(child.child_elements) > 0 :
                (q, f) = self.__create_instance_tables_query_inner_loop(elementdef=child, parent_id=parent_id,  parent_name=self.__name( next_parent_name, child.name ), parent_table_name=parent_table_name ) #next-parent-name
            else:
                local_fields.append( self.__db_field_name(child) )
                (q,f) = self.__create_instance_tables_query_inner_loop(elementdef=child, parent_id=parent_id, parent_name=next_parent_name, parent_table_name=parent_table_name ) #next-parent-name
            next_query = next_query + q
            local_fields = local_fields + f
      return (next_query, local_fields)
    
    def queries_to_populate_instance_tables(self, data_tree, elementdef, parent_name='', parent_table_name='', parent_id=0 ):
      if data_tree is None : return
      if not elementdef: return
      
      table_name = get_table_name( self.__name(parent_name, elementdef.name) )      
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
      
      (next_query, fields, values) = self.__populate_instance_tables_inner_loop(data_tree=data_tree, elementdef=elementdef, parent_name=parent_name, parent_table_name=table_name, parent_id=parent_id )
      if not values: return next_query

      queries = "INSERT INTO " + table_name + " (";
      queries = queries + self.__trim2chars(fields)
      if parent_id > 0: queries = queries + ", parent_id"
      queries = queries + ") VALUES( "
      queries = queries + self.__trim2chars(values)
      if parent_id > 0: queries = queries + ", " + str(parent_id)
      queries = queries +  ");"
      queries = queries + next_query
      return queries

    def __populate_instance_tables_inner_loop(self, data_tree, elementdef, parent_name='', parent_table_name='', parent_id=0 ):
      if data_tree is None: return
      if not elementdef : return
      local_fields = '';
      values = '';
      
      next_query = ''
      if len(elementdef.child_elements)== 0:
          if elementdef.is_repeatable :
              local_fields = self.__sanitize(elementdef.name) + ", "
              values = self.__db_format(elementdef.type, data_tree.text) + ", "      
          return (next_query, local_fields, values)
      for def_child in elementdef.child_elements:        
        data_node = None
        
        # todo - make sure this works in a case-insensitive way
        # find the data matching the current elementdef
        # todo - put in a check for root.isRepeatable
        next_parent_name = self.__name(parent_name, elementdef.name)
        if def_child.is_repeatable :
            for data_child in data_tree.iter('{'+self.namespace+'}'+def_child.name):
                next_query = next_query + self.queries_to_populate_instance_tables(data_child, def_child, next_parent_name, parent_table_name, parent_id )
        else:
            # if there are children (which are not repeatable) then flatten the table
            for data_child in data_tree.iter('{'+self.namespace+'}'+def_child.name):
                data_node = data_child
                break;
            if( len(def_child.child_elements)>0 ):
                if data_node is not None:
                    (q,f,v) = self.__populate_instance_tables_inner_loop(data_tree=data_node, elementdef=def_child, parent_name=parent_name, parent_table_name=parent_table_name )
                    next_query = next_query + q
                    local_fields = local_fields + f
                    values  = values + v
            else:
                # if there are no children, then add values to the table
                if data_child.text is not None :
                    local_fields = local_fields + self.__sanitize(def_child.name) + ", "
                    values = values + self.__db_format(def_child.type, data_child.text) + ", "
                (q, f, v) = self.__populate_instance_tables_inner_loop(data_child, def_child, next_parent_name, parent_table_name)
                next_query = next_query + q
                local_fields = local_fields + f
                values  = values + v
      return (next_query, local_fields, values)

    def __trim2chars(self, string):
        return string[0:len(string)-2]
        
    def __name(self, parent_name, child_name):
        if parent_name: 
            if parent_name.lower() != child_name.lower():
                return str(parent_name) + "_" + str(child_name)
        return str(child_name)
        
    def __get_db_type(self, type):
        if type.lower() in self.XSD_TO_DB_TYPES: 
            return self.XSD_TO_DB_TYPES[type]
        else: 
            return self.XSD_TO_DB_TYPES['default']
        
    def __db_format(self, type, text):
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
            else:
                return "'" + text.strip() + "'"        
        else:            
            return "'" + text.strip() + "'"

    # todo: put all sorts of useful db fieldname sanitizing stuff in here
    def __sanitize(self, name):
        if name.lower() == "where" or name.lower() == "when":
            return "_" + name
        else:
            return name

    def __db_field_name(self, elementdef):
        return self.__sanitize( elementdef.name ) + " " + self.__get_db_type( elementdef.type ) + ", "
    
    def __execute_queries(self, queries):
        # todo - rollback on fail
        logging.debug(queries)
        cursor = connection.cursor()
        if settings.DATABASE_ENGINE=='mysql' :
            cursor.execute(queries)            
        else:
            simple_queries = queries.split(';')
            for query in simple_queries: 
                cursor.execute(query)

    def remove_schema(self, id):
        fdds = FormDefData.objects.all().filter(id=id) 
        if fdds is None or len(fdds) == 0:
            logging.error("  Schema " + name + " could not be found. Not deleted.")
            return    
        # must remove tables first since removing form_meta automatically deletes some tables
        self.__remove_form_tables(fdds[0])
        self.__remove_form_meta(fdds[0])
        # when we delete formdefdata, django automatically deletes all associated elementdefdata
        transaction.commit()
    
    # make sure when calling this function always to confirm with the user
    def clear(self):
        """ removes all schemas found in XSD_REPOSITORY_PATH
            and associated tables. It also deletes the contents of XFORM_SUBMISSION_PATH.        
        """
        self.__remove_form_tables()
        self.__remove_form_meta()
        # when we delete formdefdata, django automatically deletes all associated elementdefdata
            
        # drop all xml data instance files stored in XFORM_SUBMISSION_PATH
        for file in os.listdir(settings.XFORM_SUBMISSION_PATH):
            file = os.path.join(settings.XFORM_SUBMISSION_PATH, file)
            logging.debug(  "Deleting " + file )
            stat = os.stat(file)
            if S_ISREG(stat[ST_MODE]) and os.access(file, os.W_OK):
                os.remove( file )
            else:
                logging.debug(  "  WARNING: Permission denied to access " + file )
                continue
        
    def __remove_form_meta(self,form=''):
        # drop all schemas, associated tables, and files
        if form == '':
            fdds = FormDefData.objects.all().filter()
        else:
            fdds = FormDefData.objects.all().filter(target_namespace=form.target_namespace)            
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
            edds = ElementDefData.objects.all().filter().order_by("-table_name")
        else:
            edds = ElementDefData.objects.all().filter(form=form).order_by("-table_name")
        for edd in edds:
            logging.debug(  "  deleting data table:" + edd.table_name )
            cursor = connection.cursor()
            cursor.execute("drop table " + edd.table_name)
