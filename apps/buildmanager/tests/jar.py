import unittest
import os
from datetime import datetime
import time
import shutil

from xformmanager.models import MetaDataValidationError
from buildmanager.jar import *

class JarTestCase(unittest.TestCase):
    
    def setUp(self):
        # set some variables we'll use to process our jar file
        self.path = os.path.dirname(__file__)
        self.jarfile = os.path.join(self.path, "Test.jar")
        self.extra_jar = os.path.join(self.path, "ExtraMetaField.jar")
        self.missing_jar = os.path.join(self.path, "MissingMetaField.jar")
        self.duplicate_jar = os.path.join(self.path, "DuplicateMetaField.jar")
        self.output_dir = os.path.join(self.path, "jarout-%s" % time.time())
        

    def tearDown(self):
        # clean the folder we created after every test
        if os.path.isdir(self.output_dir):
            shutil.rmtree(self.output_dir)
        
    
    def testExtractXForms(self):
        self.assertFalse(os.path.isdir(self.output_dir), 
                         "Directory should not exist before test")
        xforms = extract_xforms(self.jarfile, self.output_dir)
        # make sure we got back the right xforms
        self.assertEqual(2, len(xforms),
                         "Extract xforms should return two xforms")
        self.assertTrue(os.path.isdir(self.output_dir), 
                        "Directory should exist after extraction")
        filelist = os.listdir(self.output_dir)
        self.assertEqual(2, len(filelist), 
                         "There should be two xforms in the directory")
        self.assertTrue("brac_chw.xml" in filelist)
        self.assertTrue("weekly_update.xml" in filelist)

    def testValidateJar(self):
        validate_jar(self.jarfile)
        try:
            validate_jar(self.missing_jar)
            self.fail("Missing meta field did not raise an exception")
        except MetaDataValidationError, e:
            self.assertTrue(e.missing)
            self.assertFalse(e.duplicate)
            self.assertFalse(e.extra)
        try:
            validate_jar(self.extra_jar)
            self.fail("Extra meta field did not raise an exception")
        except MetaDataValidationError, e:
            self.assertTrue(e.extra)
            self.assertFalse(e.duplicate)
            self.assertFalse(e.missing)
        try:
            validate_jar(self.duplicate_jar)
            self.fail("Missing meta field did not raise an exception")
        except MetaDataValidationError, e:
            self.assertTrue(e.duplicate)
            self.assertFalse(e.missing)
            self.assertFalse(e.extra)
    
            