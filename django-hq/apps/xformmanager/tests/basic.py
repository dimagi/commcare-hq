import unittest
from xformmanager.formdefprovider import * 
from xformmanager.formmanager import FormManager

class BasicTestCase(unittest.TestCase):
    def setup(selfs):
        pass

    def testCreateFormDef(self):        
        f = open("xsd_basic.in","r")
        provider = FormDefProviderFromXSD(f)
        formDef = provider.get_formdef()
        print formDef.tostring()
	# see if output looks right
        f.close()
        pass

    def testSaveFormData(self):
        # Create a new form definition
        f = open("xsd_basic.in","r")
        manager = FormManager()
        manager.add_formdef(f)
        f.close()

        # and input one xml instance
        f = open("xml_basic.in","r")
        manager.save_form_data(f)
	# make sure tables are created the way you'd like
        f.close()
	pass

