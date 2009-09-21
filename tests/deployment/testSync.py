""" This unit test verifies that satellite server synchronization works 
It is currently designed to be run from the commcare-hq install dir, like:
<install-dir>/python tests/deployment/testSync.py
"""

""" VARIABLES """
import os
serverhost = 'localhost:8000'
#serverhost = 'test.commcarehq.org' #for the actual server
curl_command = 'c:\curl\curl.exe' #if you have curl installed on windows
#curl_command = 'curl' #if curl is in your path/linux

filedir = os.path.dirname(__file__)
DATA_DIR = os.path.join( filedir, 'data' )

""" FIXING PATH """
projectdir = os.path.realpath( os.path.join(filedir,'..' + os.sep + '..') )

import sys
sys.path.append(os.path.join(projectdir))
sys.path.append(os.path.join(projectdir, 'apps'))
sys.path.append(os.path.join(projectdir, 'rapidsms'))
sys.path.append(os.path.join(projectdir, 'rapidsms', 'apps'))

#rapidsms lib stuff
sys.path.append(os.path.join(projectdir, 'rapidsms', 'lib'))
sys.path.append(os.path.join(projectdir, 'rapidsms', 'lib','rapidsms'))
sys.path.append(os.path.join(projectdir, 'rapidsms', 'lib','rapidsms','webui'))

""" ENVIRONMENT """
import rapidsms
os.environ["RAPIDSMS_INI"] = os.path.join(projectdir,"local.ini")
os.environ["RAPIDSMS_HOME"] = projectdir
from django.core.management import setup_environ
from rapidsms.webui import settings
setup_environ(settings)

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
        schema_1 = create_xsd_and_populate("pf_followup.xsd", \
                                           "pf_followup_1.xml", path = DATA_DIR)
        populate("pf_followup_2.xml", path = DATA_DIR)
        schema_2 = create_xsd_and_populate("pf_new_reg.xsd", \
                                "pf_new_reg_1.xml", path = DATA_DIR)
        populate("pf_new_reg_2.xml", path = DATA_DIR)
        schema_3 = create_xsd_and_populate("pf_ref_completed.xsd", \
                                "pf_ref_completed_1.xml", path = DATA_DIR)
        populate("pf_ref_completed_2.xml", path = DATA_DIR)
        
        # download and check
        submissions_file = "submissions.tar"
        generate_submissions(serverhost, 'brian', 'test', latest=False, download=True, to=submissions_file)
        try:
            self._assert_tar_count_equals(submissions_file, Submission.objects.all().count())
            
        # cleanup
        finally:
            # delete all data on self
            manager = XFormManager()
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
    
    def test_sync_all_submissions(self):
        """ Tests synchronizing all data from self (no MD5s posted) """
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
    
    def test_sync_some_submissions(self):
        """ Tests synchronizing some data from self (posts a few MD5s) """
        manager = XFormManager()
    
        # populate some files
        schema_1 = create_xsd_and_populate("pf_followup.xsd", "pf_followup_1.xml", path = DATA_DIR)
        schema_2 = create_xsd_and_populate("pf_new_reg.xsd", "pf_new_reg_1.xml", path = DATA_DIR)
        schema_3 = create_xsd_and_populate("pf_ref_completed.xsd", "pf_ref_completed_1.xml", path = DATA_DIR)
        
        # get MD5 of 3 populated files
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
    
        url = 'http://%s/api/submissions/' % (serverhost)
        up = urlparse(url)
        conn = httplib.HTTPConnection(up.netloc)
        conn.request('POST', up.path, MD5_buffer, {'Content-Type': 'application/bz2', 'User-Agent': 'CCHQ-submitfromfile-python-v0.1'})
        response = conn.getresponse()
        submissions_file = "submissions.tar"
        fout = open(submissions_file, 'w+b')
        fout.write(response.read())
        fout.close()
    
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
        load_submissions(submissions_file)
        
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
    
    def test_sync_weird_submissions(self):
        """ Tests synchronizing some data from self (posts a few MD5s) """
        
        # setup - if we don't do this, we just get back "no submissions found"
        manager = XFormManager()
    
        # populate some files
        schema_1 = create_xsd_and_populate("pf_followup.xsd", "pf_followup_1.xml", path = DATA_DIR)
        schema_2 = create_xsd_and_populate("pf_new_reg.xsd", "pf_new_reg_1.xml", path = DATA_DIR)
        schema_3 = create_xsd_and_populate("pf_ref_completed.xsd", "pf_ref_completed_1.xml", path = DATA_DIR)

        url = 'http://%s/api/submissions/' % (serverhost)
        up = urlparse(url)
        conn = httplib.HTTPConnection(up.netloc)
        
        # test posting junk md5
        MD5_buffer = "sadfndan;ofansdn"
        conn.request('POST', up.path, MD5_buffer, {'Content-Type': 'application/bz2', 'User-Agent': 'CCHQ-submitfromfile-python-v0.1'})
        response = conn.getresponse().read()
        self.assertTrue( response.lower().find('poorly formatted') != -1 )

        # test posting non-existent md5s
        md5 = "e402f026c762a6bc999f9f2703efd367"
        bz2_md5 = bz2.compress(md5)
        conn.request('POST', up.path, bz2_md5, {'Content-Type': 'application/bz2', 'User-Agent': 'CCHQ-submitfromfile-python-v0.1'})
        response = conn.getresponse().read()
        submissions_file = "submissions.tar"
        fout = open(submissions_file, 'wb')
        fout.write(response)
        fout.close()
        # should get the same 3 schemas we registered above
        self._assert_tar_count_equals(submissions_file, 3)

        # test posting duplicate md5s
        string = cStringIO.StringIO()
        submits = Submission.objects.all().order_by('checksum')[:2]
        for submit in submits:
            string.write(unicode( submit.checksum ) + '\n')
            string.write(unicode( submit.checksum  ) + '\n')
        dupe_buffer = bz2.compress(string.getvalue())
        conn.request('POST', up.path, dupe_buffer, {'Content-Type': 'application/bz2', 'User-Agent': 'CCHQ-submitfromfile-python-v0.1'})
        response = conn.getresponse().read()
        submissions_file = "submissions.tar"
        fout = open(submissions_file, 'wb')
        fout.write(response)
        fout.close()
        self._assert_tar_count_equals(submissions_file, 1)

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
    
        load_submissions(submissions_file)    
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
        load_schemata(schemata_file)
        
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
        url = 'http://%s/api/xforms/?format=sync' % (serverhost)
        up = urlparse(url)
        conn = httplib.HTTPConnection(up.netloc)
        conn.request('POST', up.path, xmlns_buffer, {'Content-Type': 'application/bz2', 'User-Agent': 'CCHQ-submitfromfile-python-v0.1'})
        response = conn.getresponse()
        schemata_file = "schemata.tar"
        fout = open(schemata_file, 'w+b')
        fout.write(response.read())
        fout.close()
    
        # delete the ones just populated (d,e,f)
        manager.remove_schema(schema_2.id, remove_submissions = True)
        manager.remove_schema(schema_3.id, remove_submissions = True)
        
        # load data from sync file (d,e,f)
        load_schemata(schemata_file)
        
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
        conn.request('POST', up.path, bz2_namespace, {'Content-Type': 'application/bz2', 'User-Agent': 'CCHQ-submitfromfile-python-v0.1'})
        response = conn.getresponse().read()
        schemata_file = "schemata.tar"
        fout = open(schemata_file, 'wb')
        fout.write(response)
        fout.close()
        # should get all the schemas back
        self._assert_tar_count_equals(schemata_file, starting_schemata_count+3)

        # test posting duplicate namespaces
        string = cStringIO.StringIO()
        formdefs = FormDefModel.objects.all().order_by('target_namespace')[:2]
        for formdef in formdefs:
            string.write(unicode( formdef.target_namespace ) + '\n')
            string.write(unicode( formdef.target_namespace ) + '\n')
        dupe_buffer = bz2.compress(string.getvalue())
        conn.request('POST', up.path, dupe_buffer, {'Content-Type': 'application/bz2', 'User-Agent': 'CCHQ-submitfromfile-python-v0.1'})
        response = conn.getresponse().read()
        schemata_file = "schemata.tar"
        fout = open(schemata_file, 'wb')
        fout.write(response)
        fout.close()
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
        load_schemata(schemata_file)    
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

if __name__ == "__main__":
    real_args = [sys.argv[0]]
    if len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            argsplit = arg.split('=')
            if len(argsplit) == 2:
                if argsplit[0] == 'serverhost':
                    serverhost = argsplit[-1]                
                elif argsplit[0] == 'curlcommand':
                    curl_command = argsplit[-1]
                else:
                    raise "Error, these arguments are wrong, it should only be\nt\tserverhost=<hostname>\n\tcurlcommand=<curl command>\n\t\tand they BOTH must be there!"
            else:
                #it's not an argument we want to parse, so put it into the actual args
                real_args.append(arg)
    
    print curl_command
    unittest.main(argv=real_args)





