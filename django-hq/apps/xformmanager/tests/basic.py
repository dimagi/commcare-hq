import unittest
from xformmanager.formdefprovider import * 
from xformmanager.formmanager import FormManager
import os

class BasicTestCase(unittest.TestCase):
    def setup(selfs):
        pass

    def testCreateFormDef(self):
        """ Test that form definitions are created correctly """
        
        # ro -I'll put this back in once we've standardized on a good input file
        """f = open(os.path.join(os.path.dirname(__file__),"xsd_basic.in"),"r")
	provider = FormDefProviderFromXSD(f)
        formDef = provider.get_formdef()
        print formDef.tostring()
	# see if output looks right
        f.close()
        """
        pass

    def testSaveFormData(self):
        """ Test that a basic form definition can be created and basic form data saved """
        
        """ ro- I'll put this back in once we've standardized on a good input file
        # Create a new form definition
        f = open(os.path.join(os.path.dirname(__file__),"xsd_basic.in"),"r")
        manager = FormManager()
        manager.add_formdef(f)
        f.close()

        # and input one xml instance
        f = open(os.path.join(os.path.dirname(__file__),"xml_basic.in"),"r")
        manager.save_form_data(f)
	    # make sure tables are created the way you'd like
        f.close()
        """
        pass

