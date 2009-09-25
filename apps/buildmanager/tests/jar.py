import unittest
import os
from datetime import datetime
import time
import shutil

from xformmanager.models import MetaDataValidationError
from buildmanager.jar import *
from buildmanager.exceptions import BuildError

class JarTestCase(unittest.TestCase):
    
    def setUp(self):
        # set some variables we'll use to process our jar file
        self.path = os.path.dirname(__file__)
        path_to_data = os.path.join(self.path, "data")
        self.jarfile = os.path.join(path_to_data , "Test.jar")
        self.extra_jar = os.path.join(path_to_data , "ExtraMetaField.jar")
        self.missing_jar = os.path.join(path_to_data , "MissingMetaField.jar")
        self.duplicate_jar = os.path.join(path_to_data , "DuplicateMetaField.jar")
        self.no_xmlns_jar = os.path.join(path_to_data , "NoXmlns.jar")
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
        except BuildError, be:
            self.assertEqual(1, len(be.errors))
            e = be.errors[0]
            self.assertTrue(e.missing)
            self.assertFalse(e.duplicate)
            self.assertFalse(e.extra)
        
        # No longer have extra meta fields fail hard.  We may 
        # want to validate this better in the future.  
        validate_jar(self.extra_jar)
        try:
            validate_jar(self.duplicate_jar)
            self.fail("Duplicate meta field did not raise an exception")
        except BuildError, be:
            self.assertEqual(1, len(be.errors))
            e = be.errors[0]
            self.assertTrue(e.duplicate)
            self.assertFalse(e.missing)
            self.assertFalse(e.extra)
        try:
            validate_jar(self.no_xmlns_jar)
            self.fail("Missing XMLNS did not raise an exception")
        except BuildError, e:
            # we expect this error to say something about a missing namespace
            self.assertTrue("namespace" in unicode(e))

        
            