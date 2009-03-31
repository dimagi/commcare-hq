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

    def add_formdef(self, formdef):
        id = self.update_elementdefdef_meta(formdef)
        queries = self.queries_to_create_instance_tables(formdef, id, formdef.name, formdef.name)
        self.__execute_queries(queries)
        return id
    
    def remove_formdef(self, name):
        # update formdef meta tables
        # drop formdef data tables
        pass
    
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
        xsd_form_name = self.__get_xmlns(f)
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

    def update_elementdefdef_meta(self, formdef):
        """ save element metadata """
        ed = ElementDefData(name=str(formdef.name), type=str(formdef.type), 
                            table_name=get_table_name(formdef.target_namespace))
        ed.save()
        return ed.id

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
              ed = ElementDefData(name=str(child.name), type=str(child.type), parent_id=parent_id, 
                                  table_name = get_table_name( self.__name(next_parent_name, child.name) ) ) #next_parent_name
              ed.save()
              next_query = self.queries_to_create_instance_tables(child,  ed.id , parent_name, parent_table_name )
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
            return text.strip()
        else: 
            return "'" + text.strip() + "'"

    # todo: put all sorts of useful db fieldname sanitizing stuff in here
    def __sanitize(self, name):
        if name.lower() == "where":
            return "_" + name
        else:
            return name

    def __db_field_name(self, elementdef):
        return self.__sanitize( elementdef.name ) + " " + self.__get_db_type( elementdef.type ) + ", "
    
    #temporary measure to get target form
    # todo - fix this to be more efficient, so we don't parse the file twice
    def __get_xmlns(self, stream):
        logging.debug("Trying to parse xml_file")
        skip_junk(stream)
        try: 
            tree = etree.parse(stream)
        except:
            logging.debug("ERROR PARSING XML INSTANCE DATA")  
        root = tree.getroot()
        logging.debug("Parsing xml file successful")
        logging.debug("Find xmlns from " + root.tag)
        #todo - add checks in case we don't have a well-formatted xmlns
        r = re.search('{[a-zA-Z0-9_\.\/\:]*}', root.tag)
        if r is None:
            logging.error( "NO NAMESPACE FOUND" )
            return None
        xmlns = get_table_name( r.group(0).strip('{').strip('}') )
        logging.debug( "Xmlns is " + xmlns )
        return xmlns
    
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
        
    
