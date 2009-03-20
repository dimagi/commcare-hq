#import FormDef #can we comment these out?
#import ElementDef
from xformmanager.formdefprovider import * 
from xformmanager.formstorageprovider import *



class FormManager(object):
    """ This takes the formdef provided by formdef provider and passes it to FormStorageProvider.
    
    It also keeps track of registered forms and matches new xml instance data with existing forms.
    Both xml data and form data are then passed to formstorageprovider. 
    
    """
    
    def __init__(self):
        self.registered_forms = ''
        
        # These are default providers. Can be changed dynamically.
        self.formdef_provider = FormDefProviderFromXSD()
        self.storage_provider = FormStorageProvider()
      
    def set_formdef_provider(self, formdef_provider):
        self.formdef_provider = formdef_provider
      
    def set_storage_provider(self, storage_provider):
        self.storage_provider = storage_provider

    def add_formdef(self, stream):
        self.formdef_provider.set_input(stream)
        formdef = self.formdef_provider.get_formdef()
        self.storage_provider.add_formdef(formdef)
        #self.registered_forms.append(formdef)
        self.registered_forms = formdef
        
    #remove this function later
    def get_formdef(self):
        return self.registered_forms
      
    # not supported yet!
    def delete_formdef(self, name):
        self.storage_provider.remove_formdef(formdef)
        #self.registered_forms.remove(name)
      
    def save_form_data(self, stream_pointer):
        #check whether this matches an existing xmlns else puke
        data = FormData(stream_pointer)
        #do something to match xml to xsd
        #self.storage_provider.save_form_data(data, self.registered_forms.pop())
        self.storage_provider.save_form_data(data, self.registered_forms)
        pass
    
    def delete_form_data(self, name):
        pass
