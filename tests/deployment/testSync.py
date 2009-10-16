#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" This unit test verifies that satellite server synchronization works 
It is currently designed to be run from the commcare-hq install dir, like:
<install-dir>/python tests/deployment/testSync.py

TODO - clean this up so that we delete all submissions after each test
"""

""" VARIABLES """
import os
serverhost = 'test.commcarehq.org' #for the actual server
#serverhost = 'localhost:8000'
#serverhost = 'test.commcarehq.org' #for the actual server
#curl_command = 'c:\curl\curl.exe' #if you have curl installed on windows
curl_command = 'curl' #if curl is in your path/linux

filedir = os.path.dirname(__file__)
DATA_DIR = os.path.join( filedir, 'data' )

""" IMPORTS """
import bz2
import urllib2
import tarfile
import httplib
import unittest
import cStringIO
from urlparse import urlparse

from receiver.models import Submission
from receiver.management.commands.generate_submissions import generate_submissions
from receiver.management.commands.load_submissions import load_submissions
from xformmanager.management.commands.sync_schema import generate_schemata, load_schemata
from xformmanager.tests.util import create_xsd_and_populate, populate
from django_rest_interface import util as rest_util
from xformmanager.models import FormDefModel, Metadata
from xformmanager.manager import XFormManager
from xformmanager.xformdef import FormDef

""" TESTS """
class TestSync(unittest.TestCase):
    def setUp(self):
        self._delete_schema_from_filename("pf_followup.xsd", path = DATA_DIR)
        self._delete_schema_from_filename("pf_new_reg.xsd", path = DATA_DIR)
        self._delete_schema_from_filename("pf_ref_completed.xsd", path = DATA_DIR)
        
    def test_generate_all_submissions(self):
        """ Tests downloading all submissions from self """
        # setup
        schema_1 = create_xsd_and_populate("pf_followup.xsd", path = DATA_DIR)
        submit_1 = populate("pf_followup_1.xml", path = DATA_DIR)
        submit_2 = populate("pf_followup_2.xml", path = DATA_DIR)
        schema_2 = create_xsd_and_populate("pf_new_reg.xsd", path = DATA_DIR)
        submit_3 = populate("pf_new_reg_1.xml", path = DATA_DIR)
        submit_4 = populate("pf_new_reg_2.xml", path = DATA_DIR)
        schema_3 = create_xsd_and_populate("pf_ref_completed.xsd", path = DATA_DIR)
        submit_5 = populate("pf_ref_completed_1.xml", path = DATA_DIR)
        submit_6 = populate("pf_ref_completed_2.xml", path = DATA_DIR)
        
        # download and check
        submissions_file = "submissions.tar"
        generate_submissions(serverhost, 'brian', 'test', latest=False, download=True, to=submissions_file)
        try:
            self._assert_tar_count_equals(submissions_file, Submission.objects.all().count())
            
        # cleanup
        finally:
            # delete all data on self
            manager = XFormManager()
            submit_1.delete()
            submit_2.delete()
            submit_3.delete()
            submit_4.delete()
            submit_5.delete()
            submit_6.delete()
            manager.remove_schema(schema_1.id, remove_submissions = True)
            manager.remove_schema(schema_2.id, remove_submissions = True)
            manager.remove_schema(schema_3.id, remove_submissions = True)
    
    def test_generate_debug_submissions(self):
        """ Tests downloading some submissions from self 
            This is only useful to make sure that the test_load_diff_submissions test
            below is working properly.
        """
        #setup
        schema_1 = create_xsd_and_populate("pf_followup.xsd", \
                                "pf_followup_1.xml", path = DATA_DIR)
        populate("pf_followup_2.xml", path = DATA_DIR)
        schema_2 = create_xsd_and_populate("pf_new_reg.xsd", \
                                "pf_new_reg_1.xml", path = DATA_DIR)
        populate("pf_new_reg_2.xml", path = DATA_DIR)
        schema_3 = create_xsd_and_populate("pf_ref_completed.xsd", \
                                "pf_ref_completed_1.xml", path = DATA_DIR)
        populate("pf_ref_completed_2.xml", path = DATA_DIR)
        
        # the 'debug' flag limits the generated MD5s to a count of 5
        submissions_file = "submissions.tar"
        # debug means we only post 5 submissions (instead of all)
        generate_submissions(serverhost, 'brian', 'test', debug=True, download=True, to=submissions_file)
        try:
            self._assert_tar_count_equals(submissions_file, Submission.objects.all().count()-5)
            
        # cleanup
        finally:    
            # delete all data on self
            manager = XFormManager()
            manager.remove_schema(schema_1.id, remove_submissions = True)
            manager.remove_schema(schema_2.id, remove_submissions = True)
            manager.remove_schema(schema_3.id, remove_submissions = True)
    
    """
    ro - We do not want to run this unit test on every build, since it's
    going to generate something like 200 duplicate submission errors =b.
    To do this cleanly, we would delete all existing submissions from the db
    before running this, but silently wiping the db on the local machine
    is probably going to cause more headache than it saves.
    So we comment this test case out for now (most functionality is duplicated
    in test_generate_all_submissions anyways), but we can always add this
    back in later
    def test_sync_all_submissions(self):
        "" Tests synchronizing all data from self (no MD5s posted) ""
        manager = XFormManager()
    
        # load data
        schema_1 = create_xsd_and_populate("pf_followup.xsd", \
                                "pf_followup_1.xml", path = DATA_DIR)
        populate("pf_followup_2.xml", path = DATA_DIR)
        schema_2 = create_xsd_and_populate("pf_new_reg.xsd", \
                                "pf_new_reg_1.xml", path = DATA_DIR)
        populate("pf_new_reg_2.xml", path = DATA_DIR)
        schema_3 = create_xsd_and_populate("pf_ref_completed.xsd", \
                                "pf_ref_completed_1.xml", path = DATA_DIR)
        populate("pf_ref_completed_2.xml", path = DATA_DIR)
        populate("pf_ref_completed_3.xml", path = DATA_DIR)
        starting_submissions_count = Submission.objects.all().count()
        
        # get sync file from self
        submissions_file = "submissions.tar"
        generate_submissions(serverhost, 'brian', 'test', latest=False, download=True, to=submissions_file)
    
        # delete all data on self
        manager.remove_schema(schema_1.id, remove_submissions = True)
        manager.remove_schema(schema_2.id, remove_submissions = True)
        manager.remove_schema(schema_3.id, remove_submissions = True)
        # add schemas back
        schema_1 = create_xsd_and_populate("pf_followup.xsd", path = DATA_DIR)
        schema_2 = create_xsd_and_populate("pf_new_reg.xsd", path = DATA_DIR)
        schema_3 = create_xsd_and_populate("pf_ref_completed.xsd", path = DATA_DIR)
        
        # load data from sync file
        load_submissions(submissions_file)
        
        try:
            # verify that the submissions etc. count are correct
            self.assertEqual( starting_submissions_count, Submission.objects.all().count())
        finally:            
            # clean up
            manager.remove_schema(schema_1.id, remove_submissions = True)
            manager.remove_schema(schema_2.id, remove_submissions = True)
            manager.remove_schema(schema_3.id, remove_submissions = True)
    """
        
    def test_sync_some_submissions(self):
        """ Tests synchronizing some data from self (posts a few MD5s) """
        manager = XFormManager()
    
        # populate some files
        schema_1 = create_xsd_and_populate("pf_followup.xsd", "pf_followup_1.xml", path = DATA_DIR)
        schema_2 = create_xsd_and_populate("pf_new_reg.xsd", "pf_new_reg_1.xml", path = DATA_DIR)
        schema_3 = create_xsd_and_populate("pf_ref_completed.xsd", "pf_ref_completed_1.xml", path = DATA_DIR)
        
        # get MD5 of all current submissions
        MD5_buffer = rest_util.get_field_as_bz2(Submission, 'checksum')
        
        # populate a few more files
        submit_1 = populate("pf_followup_2.xml", path = DATA_DIR)
        submit_2 = populate("pf_new_reg_2.xml", path = DATA_DIR)
        submit_3 = populate("pf_ref_completed_2.xml", path = DATA_DIR)
        submit_4 = populate("pf_ref_completed_3.xml", path = DATA_DIR)
        starting_submissions_count = Submission.objects.all().count()
        starting_schemata_count = FormDefModel.objects.all().count()
        
        # get the difference between the first 3 files and the current
        # set of files (i.e. the last 4 files)
        submissions_file = "submissions.tar"
        self._POST_MD5s(MD5_buffer, submissions_file)
    
        # save checksums and delete the ones just populated (d,e,f)
        checksums = [ submit_1.checksum, submit_2.checksum, submit_3.checksum, submit_3.checksum ]
        
        manager.remove_data(schema_1.id, Metadata.objects.get(attachment=submit_1.xform).raw_data, \
                            remove_submission = True)
        manager.remove_data(schema_2.id, Metadata.objects.get(attachment=submit_2.xform).raw_data, \
                            remove_submission = True)
        manager.remove_data(schema_3.id, Metadata.objects.get(attachment=submit_3.xform).raw_data, \
                            remove_submission = True)
        manager.remove_data(schema_3.id, Metadata.objects.get(attachment=submit_4.xform).raw_data, \
                            remove_submission = True)
        
        # load data from sync file (d,e,f)
        load_submissions(submissions_file, "127.0.0.1:8000")
        
        try:
            # verify that the submissions etc. count are correct (d,e,f)
            self.assertEqual( starting_submissions_count, Submission.objects.all().count())
            submits = Submission.objects.all().order_by('-submit_time')[:4]
            # verify that the correct submissions were loaded
            Submission.objects.get(checksum=checksums[0])
            Submission.objects.get(checksum=checksums[1])
            Submission.objects.get(checksum=checksums[2])
            Submission.objects.get(checksum=checksums[3])
        except Submission.DoesNotExist:
            self.fail("Incorrect submission received")
        finally:
            # clean up
            manager = XFormManager()
            manager.remove_schema(schema_1.id, remove_submissions = True)
            manager.remove_schema(schema_2.id, remove_submissions = True)
            manager.remove_schema(schema_3.id, remove_submissions = True)
    
    def test_sync_dupe_submissions(self):
        """ Tests synchronizing duplicate data from self"""
        manager = XFormManager()
    
        # populate some files
        schema_1 = create_xsd_and_populate("pf_followup.xsd", "pf_followup_1.xml", path = DATA_DIR)
        schema_2 = create_xsd_and_populate("pf_new_reg.xsd", "pf_new_reg_1.xml", path = DATA_DIR)
        schema_3 = create_xsd_and_populate("pf_ref_completed.xsd", "pf_ref_completed_1.xml", path = DATA_DIR)
        starting_submissions_count = Submission.objects.all().count()
        
        # <STATE 1/>
        # get MD5 of 3 populated files
        MD5_buffer = rest_util.get_field_as_bz2(Submission, 'checksum')
        
        # add 3 dupes and 1 new file
        submit_1 = populate("pf_followup_1.xml", path = DATA_DIR)
        submit_2 = populate("pf_new_reg_1.xml", path = DATA_DIR)
        submit_3 = populate("pf_ref_completed_1.xml", path = DATA_DIR)
        
        # <STATE 2/>
        submissions_file = "submissions.tar"
        self._POST_MD5s(MD5_buffer, submissions_file)
        self._assert_tar_count_equals(submissions_file, 0)
        
        submit_4 = populate("pf_ref_completed_3.xml", path = DATA_DIR)
        
        # <STATE 3/>
        # get the difference between state 1 and state 3
        self._POST_MD5s(MD5_buffer, submissions_file)
    
        # save checksum and delete the ones just populated
        checksum_4 = submit_4.checksum
        submit_1.delete()
        submit_2.delete()
        submit_3.delete()
        submit_4.delete()
        
        # should get the same 3 schemas we registered above
        self._assert_tar_count_equals(submissions_file, 1)
        # load data from sync file (d,e,f)
        load_submissions(submissions_file, "127.0.0.1:8000")
        
        try:
            # verify that we only have 4 submissions
            self.assertEqual( starting_submissions_count+1, Submission.objects.all().count() )
            Submission.objects.get(checksum=checksum_4)
        except Submission.DoesNotExist:
            self.fail("Incorrect submission received")
        finally:
            # clean up
            manager = XFormManager()
            manager.remove_schema(schema_1.id, remove_submissions = True)
            manager.remove_schema(schema_2.id, remove_submissions = True)
            manager.remove_schema(schema_3.id, remove_submissions = True)
    
    def test_sync_weird_submissions(self):
        """ Tests synchronizing some data from self (posts a few MD5s) """
        
        # setup - if we don't do this, we just get back "no submissions found"
        manager = XFormManager()
    
        # populate some files
        schema_1 = create_xsd_and_populate("pf_followup.xsd", "pf_followup_1.xml", path = DATA_DIR)
        schema_2 = create_xsd_and_populate("pf_new_reg.xsd", "pf_new_reg_1.xml", path = DATA_DIR)
        schema_3 = create_xsd_and_populate("pf_ref_completed.xsd", "pf_ref_completed_1.xml", path = DATA_DIR)
        submissions_count = Submission.objects.count()

        url = 'http://%s/api/submissions/' % (serverhost)
        up = urlparse(url)
        conn = httplib.HTTPConnection(up.netloc)
        
        # test posting junk md5
        MD5_buffer = "sadfndan;ofansdn"
        conn.request('POST', up.path, MD5_buffer, {'Content-Type': 'application/bz2', 'User-Agent': 'CCHQ-submitfromfile-python-v0.1'})
        response = conn.getresponse().read()
        self.assertTrue( response.lower().find('poorly formatted') != -1 )

        # test posting non-existent md5s
        md5 = "e402f026c762a6bc999f9f2703efd367\n"
        bz2_md5 = bz2.compress(md5)
        submissions_file = "submissions.tar"
        self._POST_MD5s(bz2_md5, submissions_file)
        
        # should get the same 3 schemas we registered above
        self._assert_tar_count_equals(submissions_file, submissions_count)

        # test posting duplicate md5s
        string = cStringIO.StringIO()
        submits = Submission.objects.all().order_by('checksum')[:2]
        for submit in submits:
            string.write(unicode( submit.checksum ) + '\n')
            string.write(unicode( submit.checksum  ) + '\n')
        MD5s = string.getvalue()
        dupe_buffer = bz2.compress(MD5s)
        
        submissions_file = "submissions.tar"
        self._POST_MD5s(dupe_buffer, submissions_file)
        self._assert_tar_count_equals(submissions_file, submissions_count-2)

        manager.remove_schema(schema_1.id, remove_submissions = True)
        manager.remove_schema(schema_2.id, remove_submissions = True)
        manager.remove_schema(schema_3.id, remove_submissions = True)

    def test_sync_no_submissions(self):
        """ Tests synchronizing no data from self (posts all MD5s) """
        manager = XFormManager()
    
        # load data
        schema_1 = create_xsd_and_populate("pf_followup.xsd", \
                                "pf_followup_1.xml", path = DATA_DIR)
        populate("pf_followup_2.xml", path = DATA_DIR)
        schema_2 = create_xsd_and_populate("pf_new_reg.xsd", \
                                "pf_new_reg_1.xml", path = DATA_DIR)
        populate("pf_new_reg_2.xml", path = DATA_DIR)
        schema_3 = create_xsd_and_populate("pf_ref_completed.xsd", \
                                "pf_ref_completed_1.xml", path = DATA_DIR)
        populate("pf_ref_completed_2.xml", path = DATA_DIR)
        populate("pf_ref_completed_3.xml", path = DATA_DIR)
        starting_submissions_count = Submission.objects.all().count()
        
        # get sync file from self
        submissions_file = "submissions.tar"
        generate_submissions(serverhost, 'brian', 'test', download=True, to=submissions_file)
        
        # test that the received submissions file is empty
        self._assert_tar_count_equals(submissions_file, 0)
    
        load_submissions(submissions_file, "127.0.0.1:8000")    
        try:
            # verify that no new submissions were loaded
            self.assertEqual( starting_submissions_count, Submission.objects.all().count())
        finally:            
            # clean up
            manager.remove_schema(schema_1.id, remove_submissions = True)
            manager.remove_schema(schema_2.id, remove_submissions = True)
            manager.remove_schema(schema_3.id, remove_submissions = True)
    
    # a lot of similar code below as above - should modularize better
    def test_sync_all_schemata(self):
        """ Tests synchronizing all schemata from self (no xmlns posted) """
        manager = XFormManager()
    
        # load data
        schema_1 = create_xsd_and_populate("pf_followup.xsd", path = DATA_DIR)
        schema_2 = create_xsd_and_populate("pf_new_reg.xsd", path = DATA_DIR)
        schema_3 = create_xsd_and_populate("pf_ref_completed.xsd", path = DATA_DIR)
        starting_schemata_count = FormDefModel.objects.all().count()
        
        # get sync file from self
        schemata_file = "schemata.tar"
        generate_schemata(serverhost, 'brian', 'test', latest=False, download=True, to=schemata_file)
                
        manager.remove_schema(schema_1.id, remove_submissions = True)
        manager.remove_schema(schema_2.id, remove_submissions = True)
        manager.remove_schema(schema_3.id, remove_submissions = True)

        # load data from sync file
        load_schemata(schemata_file, "127.0.0.1:8000")
        
        try:
            # verify that the submissions etc. count are correct
            self.assertEqual( starting_schemata_count, FormDefModel.objects.all().count())
        finally:
            # clean up
            self._delete_schema_from_filename("pf_followup.xsd", path = DATA_DIR)
            self._delete_schema_from_filename("pf_new_reg.xsd", path = DATA_DIR)
            self._delete_schema_from_filename("pf_ref_completed.xsd", path = DATA_DIR)
    
    def test_sync_some_schemata(self):
        """ Tests synchronizing some schemata from self (posts a few xmlns) """
        manager = XFormManager()
    
        # populate some files
        schema_1 = create_xsd_and_populate("pf_followup.xsd", path = DATA_DIR)

        # get xmlns of populated schemas
        xmlns_buffer = rest_util.get_field_as_bz2(FormDefModel, 'target_namespace')
        
        # populate a few more schema
        schema_2 = create_xsd_and_populate("pf_new_reg.xsd", path = DATA_DIR)
        schema_3 = create_xsd_and_populate("pf_ref_completed.xsd", path = DATA_DIR)
        starting_schemata_count = FormDefModel.objects.all().count()
        
        # get the difference between the first schema and current state
        schemata_file = "schemata.tar"
        self._POST_XMLNS(xmlns_buffer, schemata_file)
    
        # delete the ones just populated (d,e,f)
        manager.remove_schema(schema_2.id, remove_submissions = True)
        manager.remove_schema(schema_3.id, remove_submissions = True)
        
        # load data from sync file (d,e,f)
        load_schemata(schemata_file, "127.0.0.1:8000")
        
        try:
            # verify that the schematas etc. count are correct (d,e,f)
            self.assertEqual( starting_schemata_count, FormDefModel.objects.all().count())
            self._assert_schema_registered("pf_followup.xsd", DATA_DIR)
            self._assert_schema_registered("pf_new_reg.xsd", DATA_DIR)
            self._assert_schema_registered("pf_ref_completed.xsd", DATA_DIR)
        finally:
            # clean up
            manager = XFormManager()
            manager.remove_schema(schema_1.id, remove_submissions = True)
            self._delete_schema_from_filename("pf_new_reg.xsd", path = DATA_DIR)
            self._delete_schema_from_filename("pf_ref_completed.xsd", path = DATA_DIR)
    
    def test_sync_weird_schemata(self):
        """ Tests synchronizing some data from self (posts a few MD5s) """
        
        # setup - if we don't do this, we just get back "no submissions found"
        manager = XFormManager()
    
        # populate some files
        starting_schemata_count = FormDefModel.objects.count()
        schema_1 = create_xsd_and_populate("pf_followup.xsd", path = DATA_DIR)
        schema_2 = create_xsd_and_populate("pf_new_reg.xsd", path = DATA_DIR)
        schema_3 = create_xsd_and_populate("pf_ref_completed.xsd", path = DATA_DIR)

        url = 'http://%s/api/xforms/?format=sync' % (serverhost)
        up = urlparse(url)
        conn = httplib.HTTPConnection(up.netloc)
        
        # test posting junk namespace
        namespace_buffer = "sadfndan;ofansdn"
        conn.request('POST', up.path, namespace_buffer, {'Content-Type': 'application/bz2', 'User-Agent': 'CCHQ-submitfromfile-python-v0.1'})
        response = conn.getresponse().read()
        self.assertTrue( response.lower().find('poorly formatted') != -1 )

        # test posting non-existent namespaces
        namespace = "http://zilch.com"
        bz2_namespace = bz2.compress(namespace)
        schemata_file = "schemata.tar"
        self._POST_XMLNS(bz2_namespace, schemata_file)

        # should get all the schemas back
        self._assert_tar_count_equals(schemata_file, starting_schemata_count+3)

        # test posting duplicate namespaces
        string = cStringIO.StringIO()
        formdefs = FormDefModel.objects.all().order_by('target_namespace')[:2]
        for formdef in formdefs:
            string.write(unicode( formdef.target_namespace ) + '\n')
            string.write(unicode( formdef.target_namespace ) + '\n')
        dupe_buffer = bz2.compress(string.getvalue())
        self._POST_XMLNS(dupe_buffer, schemata_file)
        self._assert_tar_count_equals(schemata_file, starting_schemata_count+1)

        manager.remove_schema(schema_1.id, remove_submissions = True)
        manager.remove_schema(schema_2.id, remove_submissions = True)
        manager.remove_schema(schema_3.id, remove_submissions = True)
    
    def test_sync_no_schemata(self):
        """ Tests synchronizing no data from self (posts all MD5s) """
        manager = XFormManager()
    
        # load data
        schema_1 = create_xsd_and_populate("pf_followup.xsd", path = DATA_DIR)
        schema_2 = create_xsd_and_populate("pf_new_reg.xsd", path = DATA_DIR)
        schema_3 = create_xsd_and_populate("pf_ref_completed.xsd", path = DATA_DIR)
        
        # get sync file from self
        schemata_file = 'schemata.tar'
        generate_schemata(serverhost, 'brian', 'test', download=True, to=schemata_file)
        
        # test that the received schemata file is empty
        self._assert_tar_count_equals(schemata_file, 0)
    
        starting_schemata_count = FormDefModel.objects.all().count()
        load_schemata(schemata_file, "127.0.0.1:8000")    
        try:
            # verify that no new schemata were loaded
            self.assertEqual( starting_schemata_count, FormDefModel.objects.all().count())
        finally:            
            # clean up
            manager.remove_schema(schema_1.id, remove_submissions = True)
            manager.remove_schema(schema_2.id, remove_submissions = True)
            manager.remove_schema(schema_3.id, remove_submissions = True)

    def tearDown(self):
        pass
    
    def _assert_tar_count_equals(self, file_name, count):
        if not tarfile.is_tarfile(file_name):
            # Mabye it's not a tar cuz it's a status message.
            fin = open(file_name, 'r')
            contents = fin.read(256)
            fin.close()
            if contents.lower().find("no ") != -1:
                self.assertEqual( 0, count)
                return
            raise Exception("%s is not a tar file" % file_name)
        tar = tarfile.open(file_name)
        tmp_dir = "unit_test_tmp"
        if os.path.exists(tmp_dir):
            filenames = os.listdir(tmp_dir)
            for file in filenames:
                os.remove(os.path.join(tmp_dir, file))
            os.rmdir(tmp_dir)            
        os.mkdir(tmp_dir)
        tar.extractall(path=tmp_dir)
        tar.close()
        filenames = os.listdir(tmp_dir)
        try:
            self.assertEqual( len(filenames), count)
        finally:
            # clean up
            for file in filenames:
                os.remove(os.path.join(tmp_dir, file))
            os.rmdir(tmp_dir)
        
    def _assert_schema_registered(self, schema, path):
        schema = open(os.path.join(path, schema), 'r')
        formdef = FormDef(schema)
        schema.close()
        try:
            formdef = FormDefModel.objects.get(target_namespace=formdef.target_namespace)
        except FormDefModel.DoesNotExist:
            self.fail("%s schema not registered!" % formdef.target_namespace)
        return

    def _delete_schema_from_filename(self, file_name, path):
        schema = open(os.path.join(path, file_name), 'r')
        formdef = FormDef(schema)
        schema.close()
        try:
            formdef = FormDefModel.objects.get(target_namespace=formdef.target_namespace)
        except FormDefModel.DoesNotExist:
            return
        manager = XFormManager()
        manager.remove_schema(formdef.id, remove_submissions=True)
    
    def _POST_MD5s(self, MD5_buffer, output_file):
        url = 'http://%s/api/submissions/' % (serverhost)
        up = urlparse(url)
        conn = httplib.HTTPConnection(up.netloc)
        conn.request('POST', up.path, MD5_buffer, {'Content-Type': 'application/bz2', 'User-Agent': 'CCHQ-submitfromfile-python-v0.1'})
        response = conn.getresponse()
        fout = open(output_file, 'w+b')
        fout.write(response.read())
        fout.close()

    def _POST_XMLNS(self, xmlns_buffer, output_file):
        url = 'http://%s/api/xforms/?format=sync' % (serverhost)
        up = urlparse(url)
        conn = httplib.HTTPConnection(up.netloc)
        conn.request('POST', up.path, xmlns_buffer, {'Content-Type': 'application/bz2', 'User-Agent': 'CCHQ-submitfromfile-python-v0.1'})
        response = conn.getresponse()
        fout = open(output_file, 'w+b')
        fout.write(response.read())
        fout.close()
        
def run():
    suite = unittest.TestLoader().loadTestsFromTestCase(TestSync)
    unittest.TextTestRunner(verbosity=2).run(suite)




