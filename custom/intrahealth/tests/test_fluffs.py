from __future__ import absolute_import
import os

from django.core import management

from corehq.apps.receiverwrapper.auth import AuthContext
from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.util.test_utils import softer_assert

import sqlalchemy

from custom.intrahealth.tests.test_utils import IntraHealthTestCase, TEST_DOMAIN
from testapps.test_pillowtop.utils import real_pillow_settings

DATAPATH = os.path.join(os.path.dirname(__file__), 'data')


class TestFluffs(IntraHealthTestCase):

    @classmethod
    @softer_assert()
    def setUpClass(cls):
        super(TestFluffs, cls).setUpClass()
        cls.table = cls.taux_sat_table
        cls.couverture = cls.couverture_table
        with open(os.path.join(DATAPATH, 'taux.xml')) as f:
            xml = f.read()
            cls.taux = submit_form_locally(
                xml, TEST_DOMAIN, auth_context=AuthContext(
                    user_id=cls.mobile_worker.get_id, domain=TEST_DOMAIN, authenticated=True
                )
            ).xform
        with open(os.path.join(DATAPATH, 'operateur.xml')) as f:
            xml = f.read()
            cls.couverture_form = submit_form_locally(
                xml, TEST_DOMAIN, auth_context=AuthContext(
                    user_id=cls.mobile_worker.get_id, domain=TEST_DOMAIN, authenticated=True
                )
            ).xform

    @classmethod
    def tearDownClass(cls):
        super(TestFluffs, cls).tearDownClass()

    def test_taux_de_satifisfaction_fluff(self):
        with real_pillow_settings():
            management.call_command(
                'ptop_reindexer_fluff',
                'IntraHealthFormFluffPillow',
            )

        query = sqlalchemy.select(
            [
                self.table.c.region_id,
                self.table.c.district_id,
                self.table.c.product_id,
                self.table.c.product_name,
                self.table.c.commandes_total,
                self.table.c.recus_total
            ],
            from_obj=self.table,
            order_by=[self.table.c.doc_id]
        )
        with self.engine.begin() as connection:
            results = list(connection.execute(query).fetchall())
        self.assertEqual(len(results), 2)

        self.assertListEqual(
            [
                self.region.get_id,
                self.district.get_id,
                self.product2.get_id,
                self.product2.name,
                26,
                23
            ],
            list(results[0])
        )

        self.assertListEqual(
            [
                self.region.get_id,
                self.district.get_id,
                self.product.get_id,
                self.product.name,
                25,
                25
            ],
            list(results[1])
        )

    def test_couverture_fluff(self):
        with real_pillow_settings():
            management.call_command(
                'ptop_reindexer_fluff',
                'IntraHealthFormFluffPillow',
            )

        query = sqlalchemy.select(
            [
                self.couverture.c.pps_name,
                self.couverture.c.registered_total_for_region,
                self.couverture.c.registered_total_for_district
            ],
            from_obj=self.couverture,
            order_by=[self.couverture.c.doc_id]
        )
        with self.engine.begin() as connection:
            results = list(connection.execute(query).fetchall())
        self.assertEqual(len(results), 1)

        self.assertListEqual(
            [
                self.pps.name,
                1,
                1
            ],
            list(results[0])
        )
