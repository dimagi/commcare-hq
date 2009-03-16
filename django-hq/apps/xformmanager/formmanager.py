#import FormDef #can we comment these out?
#import ElementDef
from xformmanager.formdefprovider import * 
from xformmanager.formstorageprovider import *

class FormManager():
  """ This will take the formdef provided by formdef provider
  and pass it to FormStorageProvider """
  
  def __init__(self):
    self.registered_forms = []
    self.formdef_provider = FormDefProviderFromXSD()
    self.storage_provider = FormStorageProvider()
    
  def set_formdef_provider(self, formdef_provider):
    self.formdef_provider = formdef_provider
    
  def set_storage_provider(self, storage_provider):
    self.storage_provider = storage_provider

  def add_formdef(self, stream_pointer):
    self.formdef_provider.set_input(stream_pointer)
    formdef = self.formdef_provider.get_formdef()
    self.storage_provider.add_formdef(formdef)
    self.registered_forms.append(formdef)
    
  # not supported yet!
  def delete_formdef(self, name):
    self.storage_provider.remove_formdef(formdef)
    self.registered_forms.remove(name)
    
  def save_form_data(self, stream_pointer):
      #check whether this matches an existing xmlns else puke
      data = FormData(stream_pointer)
      #do something to match xml to xsd
      self.storage_provider.save_form_data(data, self.registered_forms[0])
      pass
  
  def delete_form_data(self, name):
      pass
