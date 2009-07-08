from django.db import connection, transaction, DatabaseError
from xformmanager.tests.util import *
from xformmanager.models import Metadata
from receiver.models import Submission
import unittest

class BasicTestCase(unittest.TestCase):
    
    
    def testMetaData_1(self):
        create_xsd_and_populate("data/brac_chw.xsd", "data/brac_chw_1.xml")
        populate("data/brac_chw_1.xml")
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
        
        cursor.execute("SELECT * FROM x_http__dev_commcarehq_org_brac_chw_chwvisit_v0_0_1")
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
        create_xsd_and_populate("data/brac_chp.xsd", "data/brac_chp_1.xml")
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
        su = StorageUtility()
        su.clear()
        create_xsd_and_populate("data/pf_followup.xsd", "data/pf_followup_1.xml")
        populate("data/pf_followup_1.xml")
        create_xsd_and_populate("data/pf_new_reg.xsd", "data/pf_new_reg_1.xml")
        populate("data/pf_new_reg_1.xml")
        create_xsd_and_populate("data/pf_ref_completed.xsd", "data/pf_ref_completed_1.xml")
        populate("data/pf_ref_completed_1.xml")
        create_xsd_and_populate("data/mvp_mother_reg.xsd", "data/mvp_mother_reg_1.xml")
        populate("data/mvp_mother_reg_1.xml")
        populate("data/mvp_mother_reg_1.xml")
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM xformmanager_metadata order by id")
        row = cursor.fetchall()
        
        latest_submission_id = ( Attachment.objects.latest('id') ).id
        latest_formdefmodel_id = ( FormDefModel.objects.latest('id') ).id
        
        self.assertEquals(row[0][1],"PathfinderFollowUpVisit")
        self.assertEquals(row[0][9],latest_submission_id-8)
        self.assertEquals(row[0][10],1)
        self.assertEquals(row[0][11],latest_formdefmodel_id-3)
        self.assertEquals(row[1][1],"PathfinderFollowUpVisit")
        self.assertEquals(row[2][1],"PathfinderRegistratonVisit")
        self.assertEquals(row[3][1],"PathfinderRegistratonVisit")
        self.assertEquals(row[3][9],latest_submission_id-5)
        self.assertEquals(row[3][10],2)
        self.assertEquals(row[3][11],latest_formdefmodel_id-2)
        self.assertEquals(row[4][1],"PathfinderReferralVisit")
        self.assertEquals(row[5][1],"PathfinderReferralVisit")
        self.assertEquals(row[6][1],"XOLIJZVDJKLORBQUABFLVGLEA")
        self.assertEquals(row[7][1],"XOLIJZVDJKLORBQUABFLVGLEA")
        self.assertEquals(row[8][1],"XOLIJZVDJKLORBQUABFLVGLEA")
        self.assertEquals(row[8][9],latest_submission_id)
        self.assertEquals(row[8][10],3)
        self.assertEquals(row[8][11],latest_formdefmodel_id)
