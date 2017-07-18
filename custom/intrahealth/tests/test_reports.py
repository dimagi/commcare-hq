from datetime import datetime
import os

from corehq.apps.receiverwrapper.auth import AuthContext
from corehq.apps.receiverwrapper.util import submit_form_locally
from custom.intrahealth.sqldata import DispDesProducts
from custom.intrahealth.tests.test_fluffs import DATAPATH
from custom.intrahealth.tests.test_utils import IntraHealthTestCase, TEST_DOMAIN
from django.core import management

from dimagi.utils.parsing import json_format_date
from testapps.test_pillowtop.utils import real_pillow_settings


class TestReports(IntraHealthTestCase):

    @classmethod
    def setUpClass(cls):
        super(TestReports, cls).setUpClass()
        with open(os.path.join(DATAPATH, 'taux.xml')) as f:
            xml = f.read()
            cls.taux = submit_form_locally(
                xml, TEST_DOMAIN, auth_context=AuthContext(
                    user_id=cls.mobile_worker.get_id, domain=TEST_DOMAIN, authenticated=True
                )
            ).xform

        with real_pillow_settings():
            management.call_command(
                'ptop_reindexer_fluff',
                'IntraHealthFormFluffPillow'
            )

    def test_disp_des_products_report(self):
        disp_des = DispDesProducts(config=dict(
            domain=TEST_DOMAIN,
            startdate=datetime(2016, 2, 1),
            enddate=datetime(2016, 2, 29),
            visit="''",
            strsd=json_format_date(datetime(2016, 2, 1)),
            stred=json_format_date(datetime(2016, 2, 29)),
            empty_prd_code='__none__',
            region_id=self.region.get_id
        ))

        rows = disp_des.rows
        self.assertEqual(len(rows), 3)
        self.assertListEqual(
            rows,
            [
                ['Commandes', {'sort_key': 25L, 'html': 25L}, {'sort_key': 26L, 'html': 26L}],
                ['Raux', {'sort_key': 25L, 'html': 25L}, {'sort_key': 23L, 'html': 23L}],
                ['Taux', '100%', '88%']
            ]
        )
