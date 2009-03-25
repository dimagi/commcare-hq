from django.db import connection, transaction, DatabaseError
from xformmanager.models import ElementDefData, FormDefData
from xformmanager.xformdata import *
from lxml import etree
import logging

#COME BACK LATER and sanitize all inputs to avoid database keywords
# e.g. no 'where' columns, etc.

STRING = 's'
FLOAT = 'f'
DOUBLE = 'g'
INTEGER = 'i'
DATETIME = 'i'    

class StorageUtility(object):
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

    DB_STRING_TYPES = (
        'string',
        'dateTime',
        'date',
        'time',
        'anyuri'
    )
    

    """ This class handles everything that touches the database - both form and instance data."""

    def add_formdef(self, formdef):
        id = self.update_formdef_meta(formdef)
        self.create_data_tables(formdef, id, formdef.name, formdef.name)
        return id

    def remove_formdef(self, name):
        # update formdef meta tables
        # drop formdef data tables
        pass
    
    def save_form_data_matching_formdef(self, data_stream_pointer, formdef):
        logging.debug("StorageProvider: saving form data")
        tree = etree.parse(data_stream_pointer)
        root = tree.getroot()
        self.populate_data_tables(data_tree=root, elementdef=formdef, namespace=formdef.target_namespace, parent_name=formdef.name )


    def save_form_data(self, xml_file_name):
        logging.debug("RO: Getting data from xml file at " + xml_file_name)
        f = open(xml_file_name, "r")
        xsd_form_name = __get_xmlns(f)
        logging.debug("Form name is" + xsd_form_name)
        xsd = FormDefData.objects.all().filter(form_name=xsd_form_name)
        xsd_file_name = __file_name( xsd[0].target_namespace )
        f.close()
        
        logging.debug("Opening xsd file: " + xsd_file_name )
        g = open( xsd_file_name ,"r")
        formdef = FormDef(g)
        g.close()
        
        logging.debug("Saving form data from file: " + xml_file_name)
        # use seek() instead of closing/opening file again
        f = open(xml_file_name, "r")
        self.save_form_data_matching_formdef(f, formdef)
        f.close()
        logging.debug("Form data successfully saved")
        return

    def update_formdef_meta(self, formdef):
        """ save form metadata """
        ed = ElementDefData(name=str(formdef.name), type=str(formdef.type), 
                            table_name=self.__table_name(formdef.target_namespace))
        ed.save()
        return ed.id
        #fdd = FormDefData(form_name=self.__table_name(formdef.name), target_namespace=formdef.target_namespace, element_id=ed.id)
        #fdd.save()



    def create_data_tables(self, elementdef, parent_id, parent_name='', parent_table_name='' ):
        cursor = connection.cursor()
        
        #table_name = self.__table_name( parent_name )
        table_name = self.__table_name( self.__name(parent_name, elementdef.name) )
        #must create table so that parent_id references can be initialized properly
        #this is obviously quite dangerous, so makre sure to roll back on fail
        #s = "CREATE TABLE "+ table_name +" ( id INT(11) NOT NULL AUTO_INCREMENT, PRIMARY KEY (id) );"
        s = "CREATE TABLE "+ table_name +" ( id INTEGER PRIMARY KEY );"
        # MYSQL: s = "CREATE TABLE "+ table_name +" ( id INT(11) NOT NULL, PRIMARY KEY (id) );"
        logging.debug(s)
        cursor.execute(s)

        #if parent_table_name is not elementdef.name:
        #    parent_table_name = self.__name(parent_table_name, elementdef.name)              
        fields = self.__handle_children_tables(elementdef=elementdef, parent_id=parent_id, parent_name=parent_name, parent_table_name=parent_table_name )
        #fields = self.__trim2chars(fields);

        # Iterate through all the "ALTER" statements to support sqlite's limitations
        for field in fields:
            if len(field)>0:
              s = "ALTER TABLE "+ table_name + str(field)
              logging.debug(s)
              cursor.execute(s)
        #s = "ALTER TABLE "+ table_name + " ADD COLUMN parent_id INT(11);"
        #cursor.execute(s)
        
        if parent_id is not '':
            # should be NOT NULL?
            s = "ALTER TABLE " + table_name + " ADD COLUMN parent_id REFERENCES " + parent_table_name + "(id) ON DELETE SET NULL;"
            # MYSQL s = "ALTER TABLE " + table_name + " ADD FOREIGN KEY (parent_id) REFERENCES " + parent_table_name + "(id) ON DELETE SET NULL;"
        if not fields: return # move this up later
        logging.debug(s)
        cursor.execute(s)
    
    def __handle_children_tables(self, elementdef, parent_id, parent_name='', parent_table_name=''):
      """ This is 'handle' instead of 'create'(_children_tables) because not only are we 
      creating children tables, we are also gathering/passing children/field information back to the parent.
      """
      
      if not elementdef: return
      local_fields = [];

      if elementdef.is_repeatable and len(elementdef.child_elements)== 0 :
          return self.__db_field_name(elementdef)
      for child in elementdef.child_elements:
          # put in a check for root.isRepeatable
          next_parent_name = self.__name(parent_name, elementdef.name)
          if child.is_repeatable :
              # repeatable elements must generate a new table
              ed = ElementDefData(name=str(child.name), type=str(child.type), parent_id=parent_id, 
                                  table_name = self.__table_name( self.__name(next_parent_name, child.name) ) ) #next_parent_name
              ed.save()
              self.create_data_tables(child,  ed.id , parent_name, parent_table_name )
          else: 
            #assume elements of complextype alwasy have <complextype> as first child
            if len(child.child_elements) > 0 :
                local_fields = local_fields + ( self.__handle_children_tables(elementdef=child, parent_id=parent_id,  parent_name=self.__name( next_parent_name, child.name ), parent_table_name=parent_table_name ) ) #next-parent-name
            else:
                local_fields.append( self.__db_field_name(child) )
                local_fields = local_fields + ( self.__handle_children_tables(elementdef=child, parent_id=parent_id, parent_name=next_parent_name, parent_table_name=parent_table_name ) ) #next-parent-name
      return local_fields
      
    def populate_data_tables(self, data_tree, elementdef, namespace='', parent_name='', parent_table_name='' ):
      if data_tree is None : return
      if not elementdef: return
      
      field_values = self.__populate_children_tables(data_tree=data_tree, elementdef=elementdef, namespace=namespace, parent_name=parent_name, parent_table_name=parent_table_name )

      table_name = self.__table_name( self.__name(parent_name, elementdef.name) )      
      # populate the tables
      s = "INSERT INTO " + table_name + " (";
      s = s + self.__trim2chars(field_values['fields']) + ") VALUES( " + self.__trim2chars(field_values['values']) + ");"
      logging.debug(s)
      if not field_values.values: return # move this up later
      cursor = connection.cursor()

      try:
          cursor.execute(s)
      except DatabaseError:
          return

      transaction.commit_unless_managed()

    def __populate_children_tables(self, data_tree, elementdef, namespace, parent_name='', parent_table_name='' ):
      if data_tree is None: return
      if not elementdef : return
      local_fields = '';
      values = '';

      logging.debug("Saving data")      
      for def_child in elementdef.child_elements:

        data_node = None
        #come back and make sure this works in a case-insensitive way
        for data_child in data_tree.iter('{'+namespace+'}'+def_child.name):
            data_node = data_child
        
        # put in a check for root.isRepeatable
        next_parent_name = self.__name(parent_name, elementdef.name)
        if def_child.is_repeatable :
            if len(def_child.child_elements)>0 :
                # if a repeatable element has children, create a table with all children
                if data_node is not None:
                  self.populate_data_tables(data_node, def_child, namespace, next_parent_name, parent_table_name )
            else:
                # if a repeatable element has no children, create a table with just this element
                
                # find all elements matching
                for data_child in data_tree.iter('{'+namespace+'}'+def_child.name):
                    self.populate_data_tables(data_child, def_child, namespace, next_parent_name )
        else:
            if( len(def_child.child_elements)>0 ):
                
                # if there are no children, then add values to the table
                if data_node is not None:
                    field_values = self.__populate_children_tables(data_tree=data_node, elementdef=def_child, namespace=namespace, parent_name=parent_name, parent_table_name=parent_table_name )
                    local_fields = local_fields + field_values['fields']
                    values  = values + field_values['values']
                    #assume elements of complextype always have <complextyp> as first child
            else:
                # if there are children (which are not repeatable) then flatten the table
                for data_child in data_tree.iter('{'+namespace+'}'+def_child.name):
                    local_fields = local_fields + self.__sanitize(def_child.name) + ", "
                    values = values + self.__db_format(def_child.type, data_child.text) + ", "      
                    field_values = self.__populate_children_tables(data_child, def_child, namespace, next_parent_name, parent_table_name)
                    local_fields = local_fields + field_values['fields']
                    values  = values + field_values['values']
      return {'fields':local_fields, 'values':values}

    def __trim2chars(self, string):
        # ro - hack to fix recursion namespace weirdness
        #add_comma = False; if add_comma: s = s + ', ' else: add_coma = True
        return string[0:len(string)-2]
        
    def __name(self, parent_name, child_name):
        if parent_name: 
            if parent_name.lower() != child_name.lower():
                return str(parent_name) + "_" + str(child_name)
        return str(child_name)

    def __table_name(self, name):
        # check for uniqueness!
        # current hack, fix later: 122 is mysql table limit, i think
        MAX_LENGTH = 80
        start = 0
        if len(name) > MAX_LENGTH:
            start = len(name)-MAX_LENGTH
        return str(name[start:len(name)]).replace("/","_").replace(":","").replace(".","_").lower()
        
    def __get_db_type(self, type):
        if type.lower() in self.XSD_TO_DB_TYPES: 
            return self.XSD_TO_DB_TYPES[type]
        else: 
            return self.XSD_TO_DB_TYPES['default']
        
    def __db_format(self, type, text):
        if type in self.DB_STRING_TYPES:
            return "'" + text.strip() + "'"
        else: 
            return text.strip()

    # todo: put all sorts of useful db fieldname sanitizing stuff in here
    def __sanitize(self, name):
        if name.lower() == "where":
            return "_" + name
        else:
            return name

    def __db_field_name(self, elementdef):
        return " ADD COLUMN " + self.__sanitize( elementdef.name ) + " " + self.__get_db_type( elementdef.type )