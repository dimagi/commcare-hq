""" This unit test verifies that satellite server synchronization works 
It is currently designed to be run from the commcare-hq install dir, like:
<install-dir>/python tests/deployment/testSync.py
"""

""" VARIABLES """
import os
serverhost = 'localhost:8000'
curl_command = 'c:\curl\curl.exe'
DATA_DIR = "apps/xformmanager/tests/data/".replace('/',os.sep)

""" FIXING PATH """
filedir = os.path.dirname(__file__)
filedir = os.path.join(filedir,'..' + os.sep + '..')

import sys
sys.path.append(os.path.join(filedir))
sys.path.append(os.path.join(filedir, 'apps'))
sys.path.append(os.path.join(filedir, 'rapidsms'))
sys.path.append(os.path.join(filedir, 'rapidsms', 'apps'))

#rapidsms lib stuff
sys.path.append(os.path.join(filedir, 'rapidsms', 'lib'))
sys.path.append(os.path.join(filedir, 'rapidsms', 'lib','rapidsms'))
sys.path.append(os.path.join(filedir, 'rapidsms', 'lib','rapidsms','webui'))

""" ENVIRONMENT """
import rapidsms
os.environ["RAPIDSMS_INI"] = "local.ini"
os.environ["RAPIDSMS_HOME"] = os.path.abspath(os.path.dirname(__file__))
from django.core.management import setup_environ
from rapidsms.webui import settings
setup_environ(settings)

""" IMPORTS """
import urllib2
import tarfile
import httplib
import unittest
from urlparse import urlparse

from receiver.models import Submission
from receiver.management.commands.generate_submissions import get_MD5_data
from receiver.management.commands.generate_submissions import generate_submissions
from receiver.management.commands.load_submissions import load_submissions
from xformmanager.tests.util import create_xsd_and_populate, populate
from xformmanager.models import FormDefModel
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
        response = generate_submissions(serverhost, 'brian', 'test', latest=False)
        submissions_file = "submissions.tar"
        fout = open(submissions_file, 'w+b')
        fout.write(response.read())
        fout.close()
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
        response = generate_submissions(serverhost, 'brian', 'test', debug=True)
        submissions_file = "submissions.tar"
        fout = open(submissions_file, 'w+b')
        fout.write(response.read())
        fout.close()
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
        response = generate_submissions(serverhost, 'brian', 'test', latest=False)
        submissions_file = "submissions.tar"
        fout = open(submissions_file, 'w+b')
        fout.write(response.read())
        fout.close()
    
        # delete all data on self
        manager.remove_schema(schema_1.id, remove_submissions = True)
        manager.remove_schema(schema_2.id, remove_submissions = True)
        manager.remove_schema(schema_3.id, remove_submissions = True)
        # add schemas back
        schema_1 = create_xsd_and_populate("pf_followup.xsd", path = DATA_DIR)
        schema_2 = create_xsd_and_populate("pf_new_reg.xsd", path = DATA_DIR)
        schema_3 = create_xsd_and_populate("pf_ref_completed.xsd", path = DATA_DIR)
        
        # load data from sync file
        load_submissions(serverhost, submissions_file)
        
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
        MD5_buffer = get_MD5_data(Submission)
        
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
        
        
        #request = util.generate_POST_request(url, MD5_buffer)
        #response = urllib2.urlopen(request)

        submissions_file = "submissions.tar"
        fout = open(submissions_file, 'w+b')
        fout.write(response.read())
        fout.close()
    
        # delete the ones just populated (d,e,f)
        manager.remove_data(schema_1.id, submit_1.xform.form_metadata.all()[0].raw_data, \
                            remove_submission = True)
        manager.remove_data(schema_2.id, submit_2.xform.form_metadata.all()[0].raw_data, \
                            remove_submission = True)
        manager.remove_data(schema_3.id, submit_3.xform.form_metadata.all()[0].raw_data, \
                            remove_submission = True)
        manager.remove_data(schema_3.id, submit_4.xform.form_metadata.all()[0].raw_data, \
                            remove_submission = True)
        
        # load data from sync file (d,e,f)
        load_submissions(serverhost, submissions_file)
        
        try:
            # verify that the submissions etc. count are correct (d,e,f)
            self.assertEqual( starting_submissions_count, Submission.objects.all().count())
        finally:            
            # clean up
            manager = XFormManager()
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
        response = generate_submissions(serverhost, 'brian', 'test')
        submissions_file = "submissions.tar"
        fout = open(submissions_file, 'w+b')
        fout.write(response.read())
        fout.close()
        
        # test that the received submissions file is empty
        self._assert_tar_count_equals(submissions_file, 0)
    
        load_submissions(serverhost, submissions_file)    
        try:
            # verify that no new submissions were loaded
            self.assertEqual( starting_submissions_count, Submission.objects.all().count())
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
            contents = fin.read()
            fin.close()
            if contents.lower().find("no submissions") != -1:
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

