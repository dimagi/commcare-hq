from django.db import connection, transaction, DatabaseError
from xformmanager.models import ElementDefData, FormDefData
from xformmanager.formdata import *
from lxml import etree
import logging

#COME BACK LATER and sanitize all inputs to avoid database keywords
# e.g. no 'where' columns, etc.

STRING = 's'
FLOAT = 'f'
DOUBLE = 'g'
INTEGER = 'i'
DATETIME = 'i'    

class FormStorageProvider(object):
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
        self.create_data_tables(formdef)
        return id

    def remove_formdef(self, name):
        # update formdef meta tables
        # drop formdef data tables
        pass
    
    def save_form_data(self, data, formdef):
        logging.debug("StorageProvider: saving form data")
        self.populate_data_tables(data=data, elementdef=formdef, namespace=formdef.target_namespace)

    def update_formdef_meta(self, formdef):
        """ save form metadata """
        ed = ElementDefData(name=str(formdef.name), type=str(formdef.type), 
                            table_name=self.__table_name(formdef.target_namespace))
        ed.save()
        return ed.id
        #fdd = FormDefData(form_name=self.__table_name(formdef.name), target_namespace=formdef.target_namespace, element_id=ed.id)
        #fdd.save()



    def create_data_tables(self, elementdef, parent_name=''):
        fields = self.__handle_children_tables(elementdef=elementdef, parent_name=parent_name )
        fields = self.__trim2chars(fields);

        table_name = self.__table_name( self.__name(parent_name, elementdef.name) )
        s = "CREATE TABLE "+ table_name +" ( " + fields + " );"
        print s
        if not fields: return # move this up later
        cursor = connection.cursor()
        cursor.execute(s)
      
    def __handle_children_tables(self, elementdef, parent_name=''):
      """ This is 'handle' instead of 'create'(_children_tables) because not only are we 
      creating children tables, we are also gathering/passing children/field information back to the parent.
      """
      
      if not elementdef: return
      local_fields = '';

      if elementdef.is_repeatable and len(elementdef.child_elements)== 0 :
          return self.__db_field_name(elementdef.name)
      for child in elementdef.child_elements:
          # put in a check for root.isRepeatable
          next_parent_name = self.__name(parent_name, elementdef.name)
          if child.is_repeatable :
              # repeatable elements must generate a new table
              ed = ElementDefData(name=str(child.name), type=str(child.type),
                                  table_name = self.__table_name( self.__name(next_parent_name, child.name) ) )
              ed.save()
              self.create_data_tables(child, next_parent_name )
          else: 
            #assume elements of complextype alwasy have <complextype> as first child
            if len(child.child_elements) > 0 :
                local_fields = local_fields + self.__handle_children_tables(elementdef=child, parent_name=self.__name( next_parent_name, child.name ) )
            else:
                local_fields = local_fields + self.__db_field_name(child) 
                local_fields = local_fields + self.__handle_children_tables(elementdef=child, parent_name=next_parent_name )
      return local_fields


  
    def populate_data_tables(self, data, elementdef, namespace='', parent_name='' ):
      if data is None : return
      if not elementdef: return
      
      field_values = self.__populate_children_tables(data=data, elementdef=elementdef, namespace=namespace, parent_name=parent_name )
      
      # populate the tables
      s = "INSERT INTO " + self.__table_name( self.__name(parent_name, elementdef.name) ) + " (";
      s = s + self.__trim2chars(field_values['fields']) + ") VALUES( " + self.__trim2chars(field_values['values']) + ");"
      logging.debug(s)
      if not field_values.values: return # move this up later
      cursor = connection.cursor()

      try:
          cursor.execute(s)
      except DatabaseError:
          return

      transaction.commit_unless_managed()

    def __populate_children_tables(self, data, elementdef, namespace, parent_name='' ):
      if data is None: return
      if not elementdef : return
      local_fields = '';
      values = '';

      logging.debug("Saving data")      
      for child in elementdef.child_elements:
        # put in a check for root.isRepeatable
        next_parent_name = self.__name(parent_name, elementdef.name)
        if child.is_repeatable :
            if len(child.child_elements)>0 :
                self.populate_data_tables(data, child, namespace, next_parent_name )
            else:
                elements = data.xpath(child.xpath, namespaces={'x':namespace})
                for element in elements:
                    self.populate_data_tables(element, child, namespace, next_parent_name )
        else:
            if( len(child.child_elements)>0 ):
                # get child iterator
                field_values = self.__populate_children_tables(data=data, elementdef=child, namespace=namespace, parent_name=parent_name )
                local_fields = local_fields + field_values['fields']
                values  = values + field_values['values']
                #assume elements of complextype alwasy have <complextype> as first child
            else:
                elements = data.xpath(child.xpath, namespaces={'x':namespace})
                for element in elements:
                    local_fields = local_fields + self.__sanitize(child.name) + ", "
                    values = values + self.__quote(child.type, element.text) + ", "
      
      # ah, python... but is this bad form?
      print local_fields
      print values
      return {'fields':local_fields, 'values':values}

    def __trim2chars(self, string):
        # ro - hack to fix recursion namespace weirdness
        #add_comma = False; if add_comma: s = s + ', ' else: add_coma = True
        return string[0:len(string)-2]
        
    def __name(self, parent_name, child_name):
        if parent_name: return str(parent_name) + "_" + str(child_name)
        else: return str(child_name)

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
        
    def __quote(self, type, text):
        if type in self.DB_STRING_TYPES:
            return "'" + text + "'"
        else: 
            return text

    # todo: put all sorts of useful db fieldname sanitizing stuff in here
    def __sanitize(self, name):
        if name.lower() == "where":
            return "_" + name
        else:
            return name

    def __db_field_name(self, elementdef):
        return self.__sanitize( elementdef.name ) + " " + self.__get_db_type( elementdef.type ) + ", "