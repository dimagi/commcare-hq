import os
from datetime import datetime, timedelta
from rapidsms.tests.scripted import TestScript
import reporters.app as reporters_app
from reporters.models import ReporterGroup, PersistantBackend
from hq.models import Organization, Domain, ReporterProfile
from receiver.models import Submission, Attachment
from xformmanager.tests.util import *
from reports.sms.brac import *
from hq.tests.util import *

class BracTestCase(TestScript):
    apps = [ reporters_app.App ]
    
    def setUp(self):
        clear_data()
        
        TestScript.setUp(self, default_lang='sw')
        self.domain = Domain(name='mockdomain')
        self.domain.save()
        chws = ReporterGroup(title="mocksupes")
        chws.save()
        chvs = ReporterGroup(title="mocksubs")
        chvs.save()
        org = Organization(name="mockorg", domain=self.domain)
        org.members = chvs
        org.supervisors = chws
        org.save()
        
        backend = PersistantBackend.objects.get_or_create(slug=self.backend.slug)[0]
        self.sub, self.sub_profile = create_active_reporter_and_profile(backend, self.domain, phone_number="306", username='lucy')
        self.supe, self.supe_profile = create_active_reporter_and_profile(backend, self.domain, phone_number="3093", username='supe')
        
        self.sub.groups.add(chvs)
        self.supe.groups.add(chws)

        path = os.path.dirname(__file__)
        self.formdefmodel = create_xsd_and_populate("data/brac_chp.xsd", 
                                                    domain=self.domain, 
                                                    path=path)
        self.submit = populate("data/brac_chp_1.xml", domain=self.domain,
                               path=path)
        self.submit.submit_time = datetime.now() - timedelta(days=3)
        self.submit.save()
        
        self.router.start()

    def tearDown(self):
        # MUST clear storageutility first (since it deletes manually)
        su = StorageUtility()
        su.clear()
        # all other deletions are automatically handled by django
        self.domain.delete()
        self.router.stop()
    
    def test_send_activity_to_reporter(self):
        send_activity_to_reporter(self.router, self.sub_profile, "lucy", 5 )
        # Sorry for the trouble lucy. You have submitted 5 forms this week. 
        # Please remember to fill and send the complete reports every week. 
        # If the number is incorrect, call Gayo 0786151272.
        script = """
            306 < Pole kwa kazi lucy. Umetuma fomu 5 wiki hii. Tafadhali kumbuka kujaza fomu na kutuma kila wiki. Kama namba ya fomu si sahihi bip 0786151272.
        """
        self.runScript(script)

    def test_send_activity_to_super(self):
        context = {'chv':self.sub_profile, 'count': 5 }
        send_activity_to_super(self.router, self.supe_profile, context)
        # lucy has submitted 5 forms this week. Please do follow up and ask what seems to be the problem.
        script = """
            3093 < lucy ametuma fomu 5 wiki hii. Tafadhali naomba umfuatilie ujue nini ni tatizo.
        """
        self.runScript(script)
    
    def test_send_summary_activity_to_reporter(self):
        self.sub_profile.forms_this_week = 10
        context = { 'group_members':[self.sub_profile] }
        send_summary_activity_to_reporter(self.router, self.sub_profile, context )
        # lucy submitted 10 forms
        script = """
            306 < ripoti ya jumla kwa wote: lucy = 10
        """
        self.runScript(script)
    
    def test_alert_delinquent_reporter(self):
        # last seen 3 days ago
        alert_delinquent_reporter(self.router, self.sub_profile, {'last_seen':3 } )
        # 306 < Hi lucy, we haven't received any forms from you for the last 3 days. Please send your forms.
        script = """
            306 < Dada lucy hatujapokea fomu yeyote toka kwako kwa siku 3 sasa, tafadhali naomba ututume fomu.
        """
        self.runScript(script)
    
    def test_send_summary_delinquent_to_super(self):
        context = { 'delinquent_reporterprofiles':[self.sub_profile] }
        send_summary_delinquent_to_super(self.router, self.supe_profile, context)    
        # 3093 < lucy has not sent any forms for 2 or more days. Please follow up to determine the problem.
        script = """
            3093 < lucy hawajatuma fomu zao kwa zaidi ya siku 2, tafadhali naomba ufuatilie ujue nini tatizo.
        """
        self.runScript(script)
    
    def test_activity_report(self):
        activity_report(self.router, self.domain)
        # Sorry for the trouble lucy. You have submitted 1 forms this week. Please remember to fill and send the complete reports every week. If the number is incorrect, call Gayo 0786151272.
        # lucy has submitted 1 forms this week. Please do follow up and ask what seems to be the problem.
        # summary report
        script = """
            306 < Pole kwa kazi lucy. Umetuma fomu 1 wiki hii. Tafadhali kumbuka kujaza fomu na kutuma kila wiki. Kama namba ya fomu si sahihi bip 0786151272.
            3093 < lucy ametuma fomu 1 wiki hii. Tafadhali naomba umfuatilie ujue nini ni tatizo.
            306 < ripoti ya jumla kwa wote: lucy = 1 
        """
        self.runScript(script)

    def test_delinquent_report(self):
        delinquent_report(self.router, self.domain)
        # 306 < Hi lucy, we haven't received any forms from you for the last 3 days. Please send your forms.
        # 3093 < lucy has not sent any forms for 2 or more days. Please follow up to determine the problem.
        script = """
            306 < Dada lucy hatujapokea fomu yeyote toka kwako kwa siku 3 sasa, tafadhali naomba ututume fomu.
            3093 < lucy hawajatuma fomu zao kwa zaidi ya siku 2, tafadhali naomba ufuatilie ujue nini tatizo.
        """
        self.runScript(script)
