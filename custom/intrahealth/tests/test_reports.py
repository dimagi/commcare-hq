from __future__ import absolute_import
from __future__ import unicode_literals
from copy import copy
from datetime import datetime
import os

from corehq.apps.receiverwrapper.auth import AuthContext
from corehq.apps.receiverwrapper.util import submit_form_locally
from custom.intrahealth.sqldata import DispDesProducts, PPSAvecDonnees
from custom.intrahealth.tests.test_fluffs import DATAPATH
from custom.intrahealth.tests.test_utils import IntraHealthTestCase, TEST_DOMAIN
from django.core import management
import xml.etree.ElementTree as ElementTree

from dimagi.utils.parsing import json_format_date
from testapps.test_pillowtop.utils import real_pillow_settings
from io import open


class TestReports(IntraHealthTestCase):

    @classmethod
    def setUpClass(cls):
        super(TestReports, cls).setUpClass()
        with open(os.path.join(DATAPATH, 'taux.xml'), encoding='utf-8') as f:
            xml = f.read()
            xml_obj = ElementTree.fromstring(xml)
            xml_obj[2][4].text = cls.mobile_worker.get_id
            xml = ElementTree.tostring(xml_obj)
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
        cls.config = dict(
            domain=TEST_DOMAIN,
            startdate=datetime(2016, 2, 1),
            enddate=datetime(2016, 2, 29),
            visit="''",
            strsd=json_format_date(datetime(2016, 2, 1)),
            stred=json_format_date(datetime(2016, 2, 29)),
            empty_prd_code='__none__',
        )

    def test_disp_des_products_report(self):
        config = copy(self.config)
        config['region_id'] = self.region.get_id
        disp_des = DispDesProducts(config=config)

        rows = disp_des.rows
        self.assertEqual(len(rows), 3)
        self.assertListEqual(
            rows,
            [
                ['Commandes', {'sort_key': 25, 'html': 25}, {'sort_key': 26, 'html': 26}],
                ['Raux', {'sort_key': 25, 'html': 25}, {'sort_key': 23, 'html': 23}],
                ['Taux', '100%', '88%']
            ]
        )

    def test_pps_report(self):
        self.assertEqual(PPSAvecDonnees(self.config).rows, [])
        config = copy(self.config)
        config['region_id'] = self.region.get_id
        self.assertEqual(PPSAvecDonnees(config).rows, [])
