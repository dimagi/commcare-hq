from django.db import connection, transaction, DatabaseError
from ccformmanager.models import ElementDefData, FormDefData
from ccformmanager.formdata import *


class FormStorageProvider():
  def add_formdef(self, formdef):
      #should instead create two functions and pass functions to a traverse function
      self.update_formdef_meta(formdef)
      self.create_tables(formdef, formdef.name)
        
  def remove_formdef(self, name):
      # implement later
      # update formdef meta tables
      # drop formdef data tables
      pass

  def save_form_data(self, data, formdef):
      s = "INSERT INTO " + self.get_table_name(formdef.name) + " (";
      fields = ''
      values = ''

      iter = data.child_iterator()
      for child in formdef.child_elements:
          #check whatever appropriate elements are in 'data
          fields = fields + child.name + ", "
          values = values + "'" + iter.next().text + "', "
          #self.save_form_data(SOMETHING, child)
      if not values: return 
      s = s + self.__trim2chars(fields) + ") VALUES( " + self.__trim2chars(values) + ");"
      cursor = connection.cursor()
      cursor.execute(s)
      transaction.commit_unless_managed()
      
      """except DatabaseError: To be threadsafe, updates/inserts are allowed to fail silently
      transaction.rollback()
           return False
             else:
                 transaction.commit_unless_managed()
                 return True"""

  def update_formdef_meta(self, formdef):
      # save form metadata
      ed = ElementDefData(name=str(formdef.name), datatype=str(formdef.type), 
                          table_name=self.get_table_name(formdef.xmlns))
      ed.save()
      fdd = FormDefData(form_name=formdef.name, xmlns=formdef.xmlns, element_id=ed.id)
      fdd.save()

      #iterate through children and create element_meta as needed
      #ed = ElementDefData(name=str(formdef.name), datatype=str(formdef.type), 
      #                    table_name=self.get_table_name(formdef.name))
      pass
  
  def get_table_name(self, name):
      return str(name).replace("/","_").replace(":","").replace(".","_").lower()
  
  def create_tables(self, elementdef, form_name):
    # create main form table
    if not elementdef.child_elements : return
    s = "CREATE TABLE "+ self.get_table_name(elementdef.name) +" ( "
    fields = ''
    for child in elementdef.child_elements:
      #add_comma = False; if add_comma: s = s + ', ' else: add_coma = True
      #if child.tag.find("element") > -1: # FIX THIS
      fields = fields + str(child.name) + " VARCHAR(100), "
      self.create_tables(child, form_name)
    if not fields: return
    s = s + self.__trim2chars(fields) + ");"
    print s
    cursor = connection.cursor()
    cursor.execute(s)

    #once that works, iterate through children and create child tables
    
  def __trim2chars(self, string):
      # ro - hack to fix recursion namespace weirdness
      return string[0:len(string)-2]