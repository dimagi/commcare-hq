from django.test.testcases import TestCase
from corehq.apps.reports.dodoma import get_household_verification_data

def mk_json_sub(userID, caseID, time, last_hvid, next_hvid):
    return {
        'received_on': time,
        'form': {
            'meta': {
                'userID': userID,
            },
            'case': {
                'case_id': caseID,
            },
            'last_hvid': last_hvid,
            'next_hvid': next_hvid,
        },
    }

XMLNS = 'http://openrosa.org/formdesigner/9DAACA82-A414-499A-9C40-BC43775CEE79'

def mk_xml_sub(userID, caseID, time, last_hvid, next_hvid):
    xmlns = XMLNS
    return """<data xmlns="{xmlns}">
        <meta>
            <userID>{userID}</userID>
        </meta>
        <case>
            <case_id>{caseID}</case_id>
        </case>
        <household_verification>{last_hvid}</household_verification>
        <followup_id>{next_hvid}</followup_id>
    </data>""".format(**locals())

get_data = lambda mk_sub: [
    mk_sub('DANNY', 'danny01', '2011-05-01', '000', '001'),
    mk_sub('DANNY', 'danny01', '2011-05-02', '001', '002'),

    mk_sub('DANNY', 'danny02', '2011-05-01', '010', '011'),
    mk_sub('DANNY', 'danny02', '2011-05-02', '011', '012'),
    mk_sub('DANNY', 'danny02', '2011-05-03', '012', '013'),
    mk_sub('DANNY', 'danny02', '2011-05-04', '013', '014'),
    
    mk_sub('JOHAN', 'johan01', '2011-05-01', '100', '101'),
    mk_sub('JOHAN', 'johan01', '2011-05-02', '10!', '102'),
    mk_sub('JOHAN', 'johan01', '2011-05-03', '102', '103'),

    mk_sub('JOHAN', 'johan02', '2011-05-01', '110', '111'),
    mk_sub('JOHAN', 'johan02', '2011-05-02', '111', '112'),
    mk_sub('JOHAN', 'johan02', '2011-05-03', '113', '114'),
    mk_sub('JOHAN', 'johan02', '2011-05-04', '112', '113'),
    mk_sub('JOHAN', 'johan02', '2011-05-05', '114', '115'),
    mk_sub('JOHAN', 'johan02', '2011-05-06', '115', '116'),
]



class HouseholdVerificationTest(TestCase):
#    def testView(self):
#        xml_subs = get_data(mk_xml_sub)
#        domain = 'dodoma'
#        for sub in xml_subs:
#            spoof_submission(domain, sub, hqsubmission=False)
#        c = Client()
#        stats = _household_verification_json(domain=domain)
#        self._helper(stats)
    def testData(self):
        stats = get_household_verification_data(
            get_data(mk_json_sub),
            last_hvid_path=['last_hvid'],
            next_hvid_path=['next_hvid'],
        )
        self._helper(stats)

    def _helper(self, stats):
        self.assertEqual(stats[0]['userID'], 'DANNY')
        self.assertEqual(stats[0]['total'], 4)
        self.assertEqual(stats[0]['correct'], 4)
        
        self.assertEqual(stats[1]['userID'], 'JOHAN')
        self.assertEqual(stats[1]['total'], 7)
        self.assertEqual(stats[1]['correct'], 3)