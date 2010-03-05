from django.db import connection, transaction, DatabaseError
from xformmanager.tests.util import *
from xformmanager.models import Metadata, MetaDataValidationError
from xformmanager.manager import XFormManager, FormDefError
from receiver.models import Submission, Attachment, SubmissionHandlingOccurrence
import unittest
from datetime import datetime, timedelta 

class MetaTestCase(unittest.TestCase):
    
    def setUp(self):
        # clean up, in case some other tests left some straggling
        # form data, we want to start with a clean test environment
        # each time.
        clear_data()
        mockdomain = Domain.objects.get_or_create(name='metadomain')[0]
        self.domain = mockdomain
        

    def testMetaData_1(self):
        create_xsd_and_populate("data/brac_chw.xsd", "data/brac_chw_1.xml", self.domain)
        populate("data/brac_chw_1.xml", domain=self.domain)
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM xformmanager_metadata where formname='BRAC CHW visiting CHP'" )
        row = cursor.fetchone()
        self.assertEquals(row[1],"BRAC CHW visiting CHP")
        self.assertEquals(row[2],"0.0.1")
        self.assertEquals(row[3],"P6PH9SR0TKCO6RVDL4YML1D2Y")
        if settings.DATABASE_ENGINE=='mysql' :
            self.assertEquals(row[4],datetime(2008,1,8,11,55,49))
            self.assertEquals(row[5],datetime(2008,1,8,12,8,39))
        else:
            self.assertEquals(row[4],datetime(2008,1,8,11,55,49,977))
            self.assertEquals(row[5],datetime(2008,1,8,12,8,39,258))
        self.assertEquals(row[6],"cary")
        self.assertEquals(row[7],"99")
        self.assertEquals(row[8],"Z6WRHCRXYQO1C1V6B2SB3RBG8")
        
        cursor.execute("SELECT * FROM schema_metadomain_brac_chw_chwvisit_v0_0_1")
        row = cursor.fetchone()
        self.assertEquals(row[0],1)
        # checks to make sure that non-standard meta fields remain in the generated data table
        self.assertEquals(row[3],"0.0.5") # this is commcareversion number
        self.assertEquals(row[10],"worker")
        self.assertEquals(row[11],3)
        """ use these when we finally remove meta info from generate data tables
        self.assertEquals(row[1],"0.0.5") # this is commcareversion number
        self.assertEquals(row[2],"worker")
        self.assertEquals(row[3],3)
        """
        
    def testMetaData_2(self):
        create_xsd_and_populate("data/brac_chp.xsd", "data/brac_chp_1.xml", self.domain)
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM xformmanager_metadata where formname='BRACCHPHomeVisit'" )
        row = cursor.fetchone()
        self.assertEquals(row[1],"BRACCHPHomeVisit")
        self.assertEquals(row[2],"0.0.1")
        self.assertEquals(row[3],"WK13O6ST8SWZVXLAI68B9YZWK")
        if settings.DATABASE_ENGINE=='mysql' :
            self.assertEquals(row[4],datetime(2009,4,30,11,17,25))
            self.assertEquals(row[5],datetime(2009,4,30,11,21,29))
        else:
            self.assertEquals(row[4],datetime(2009,4,30,11,17,25,89))
            self.assertEquals(row[5],datetime(2009,4,30,11,21,29,512))
        self.assertEquals(row[6],"lucy")
        self.assertEquals(row[7],"6")
        self.assertEquals(row[8],"RW07SHOPTWGAOJKUQJJJN215D")

    def testMetaData_3(self):
        create_xsd_and_populate("data/pf_followup.xsd", "data/pf_followup_1.xml", self.domain)
        populate("data/pf_followup_2.xml", domain=self.domain)
        create_xsd_and_populate("data/pf_new_reg.xsd", "data/pf_new_reg_1.xml", self.domain)
        populate("data/pf_new_reg_2.xml", domain=self.domain)
        create_xsd_and_populate("data/pf_ref_completed.xsd", "data/pf_ref_completed_1.xml", self.domain)
        populate("data/pf_ref_completed_2.xml", domain=self.domain)
        create_xsd_and_populate("data/mvp_mother_reg.xsd", "data/mvp_mother_reg_1.xml", self.domain)
        populate("data/mvp_mother_reg_2.xml", domain=self.domain)
        populate("data/mvp_mother_reg_3.xml", domain=self.domain)
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM xformmanager_metadata order by id")
        row = cursor.fetchall()
        
        latest_attachment_id = ( Attachment.objects.latest('id') ).id
        latest_formdefmodel_id = ( FormDefModel.objects.latest('id') ).id
        
        self.assertEquals(row[0][1],"PathfinderFollowUpVisit")
        self.assertEquals(row[0][9],latest_attachment_id-8)
        self.assertEquals(row[0][10],1)
        self.assertEquals(row[0][11],latest_formdefmodel_id-3)
        self.assertEquals(row[1][1],"PathfinderFollowUpVisit")
        self.assertEquals(row[2][1],"PathfinderRegistratonVisit")
        self.assertEquals(row[3][1],"PathfinderRegistratonVisit")
        self.assertEquals(row[3][9],latest_attachment_id-5)
        self.assertEquals(row[3][10],2)
        self.assertEquals(row[3][11],latest_formdefmodel_id-2)
        self.assertEquals(row[4][1],"PathfinderReferralVisit")
        self.assertEquals(row[5][1],"PathfinderReferralVisit")
        self.assertEquals(row[6][1],"XOLIJZVDJKLORBQUABFLVGLEA")
        self.assertEquals(row[7][1],"XOLIJZVDJKLORBQUABFLVGLEA")
        self.assertEquals(row[8][1],"XOLIJZVDJKLORBQUABFLVGLEA")
        self.assertEquals(row[8][9],latest_attachment_id)
        self.assertEquals(row[8][10],3)
        self.assertEquals(row[8][11],latest_formdefmodel_id)
        
    def testSubmissionCount(self):
        create_xsd_and_populate("data/pf_followup.xsd", domain=self.domain)
        today = datetime.now().date()
        tomorrow = today + timedelta(days=1)
        day_after_tomorrow = today + timedelta(days=2)
        yesterday = today - timedelta(days=1)
        for i in range(1, 6):
            submission = populate("data/pf_followup_%s.xml" % i, domain=self.domain)
            meta = Metadata.objects.get(attachment=submission.xform)
            self.assertEqual(i, meta.get_submission_count(today, tomorrow, False))
            self.assertEqual(1, meta.get_submission_count(today, tomorrow, True))
            self.assertEqual(0, meta.get_submission_count(yesterday, today, False))
            self.assertEqual(0, meta.get_submission_count(tomorrow, day_after_tomorrow, False))
            self.assertEqual(i, meta.get_submission_count(yesterday, day_after_tomorrow, False))
            self.assertEqual(1, meta.get_submission_count(yesterday, day_after_tomorrow, True))
            
    def testDuplicates(self):
        create_xsd_and_populate("data/pf_followup.xsd", domain=self.domain)
        running_count = 0
        self.assertEqual(running_count, len(Metadata.objects.all()))
        
        for i in range(1, 6):
            populate("data/pf_followup_%s.xml" % i, domain=self.domain)
            # the first one should update the count.  The rest should not
            running_count = running_count + 1
            self.assertEqual(running_count, len(Metadata.objects.all()))
            for j in range(0, 3):
                logging.warn("EXPECTING A 'duplicate submission' ERROR NOW:")
                populate("data/pf_followup_%s.xml" % i, domain=self.domain)
                self.assertEqual(running_count, len(Metadata.objects.all()))
    
    def testReSubmit(self):
        # original submission
        submission = populate("data/pf_followup_1.xml", domain=self.domain)
        self.assertEquals(submission.is_orphaned(),True)
        # register schema
        create_xsd_and_populate("data/pf_followup.xsd", domain=self.domain)
        # xformmanagger resubmission
        xformmanager = XFormManager()
        status = xformmanager.save_form_data(submission.xform)
        self.assertEquals(status,True)
    
    def testSubmitHandling(self):
        create_xsd_and_populate("data/pf_followup.xsd", domain=self.domain)
        self.assertEqual(0, len(Metadata.objects.all()))
        self.assertEqual(0, len(Submission.objects.all()))
        self.assertEqual(0, len(SubmissionHandlingOccurrence.objects.all()))
        
        # this should create a linked submission
        populate("data/pf_followup_1.xml", domain=self.domain)
        
        self.assertEqual(1, len(Metadata.objects.all()))
        self.assertEqual(1, len(Submission.objects.all()))
        submission = Submission.objects.all()[0]
        self.assertEqual(1, len(SubmissionHandlingOccurrence.objects.all()))
        way_handled = SubmissionHandlingOccurrence.objects.all()[0]
        self.assertEqual(submission, way_handled.submission)
        # add check for a count from this user, equal to one
        self.assertEqual("1", way_handled.message)
        self.assertEqual("xformmanager", way_handled.handled.app)
        self.assertEqual("instance_data", way_handled.handled.method)
        self.assertFalse(submission.is_orphaned())
        
        # these should NOT create a linked submission.  No schema
        logging.warn("\nEXPECTING AN ERROR NOW:")
        populate("data/pf_new_reg_1.xml", domain=self.domain)
        logging.warn("EXPECTING AN ERROR NOW:")
        populate("data/pf_new_reg_2.xml", domain=self.domain)
        logging.warn("EXPECTING AN ERROR NOW:")
        populate("data/pf_ref_completed_1.xml", domain=self.domain)
        
        self.assertEqual(1, len(Metadata.objects.all()))
        self.assertEqual(4, len(Submission.objects.all()))
        for new_submission in Submission.objects.all():
            if new_submission == submission:
                self.assertFalse(new_submission.is_orphaned())
            else:
                self.assertTrue(new_submission.is_orphaned())
        self.assertEqual(1, len(SubmissionHandlingOccurrence.objects.all()))
        self.assertEqual(way_handled, SubmissionHandlingOccurrence.objects.all()[0])

    def testSubmissionHandling(self):
        count = len(SubmissionHandlingOccurrence.objects.all())
        self.assertEquals(0,count)
        formdefmodel_6 = create_xsd_and_populate("data/pf_followup.xsd", "data/pf_followup_1.xml", self.domain)
        count = len(SubmissionHandlingOccurrence.objects.all())
        self.assertEquals(1,count)

    def testNoMetadata(self):
        logging.warn("EXPECTING A 'No metadata found' ERROR NOW:")
        create_xsd_and_populate("data/brac_chp.xsd", "data/brac_chp_nometa.xml", self.domain)
        # raises a Metadata.DoesNotExist error on fail
        metadata = Metadata.objects.get()
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM schema_metadomain_test_no_meta")
        row = cursor.fetchone()
        self.assertEquals(row[0],1)
        self.assertEquals(int(row[10]),132) # this is commcareversion number
        self.assertEquals(row[11],"EDINA KEJO")

    def testEmptySubmission(self):
        logging.warn("EXPECTING A 'No metadata found' ERROR NOW:")
        create_xsd_and_populate("data/brac_chp.xsd", "data/brac_chp_nothing.xml", self.domain)
        # raises a Metadata.DoesNotExist error on fail
        metadata = Metadata.objects.get()
        # empty submissions do not create rows in the data tables
    
    def tearDown(self):
        # duplicates setUp, but at least we know we're being clean
        clear_data()
