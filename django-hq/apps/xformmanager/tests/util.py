from xformmanager.storageutility import *
from xformmanager.xformdef import *
import logging

def create_xsd_and_populate(xsd_file_name, xml_file_name=''):
    # Create a new form definition
    su = StorageUtility()
    
    f = open(os.path.join(os.path.dirname(__file__),xsd_file_name),"r")
    formDef = FormDef(f)
    fdd = su.add_schema(formDef)
    f.close()
    print formDef
    
    logging.debug("1")
    if xml_file_name is not None:
        logging.debug("2")
        # and input one xml instance
        f = open(os.path.join(os.path.dirname(__file__),xml_file_name),"r")
        su.save_form_data_matching_formdef(f, formDef)
        # make sure tables are created the way you'd like
        f.close()
    logging.debug("3")
    
    return fdd
