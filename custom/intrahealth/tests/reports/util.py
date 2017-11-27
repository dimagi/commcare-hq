from __future__ import absolute_import

from datetime import datetime
from django.test.testcases import TestCase

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.locations.models import SQLLocation, LocationType
from corehq.apps.products.models import SQLProduct
from corehq.apps.users.models import WebUser
from corehq.sql_db.connections import connection_manager
from custom.intrahealth.models import IntraHealthFluff, CouvertureFluff, TauxDeRuptureFluff, RecouvrementFluff, \
    TauxDeSatisfactionFluff, LivraisonFluff


class ReportTestCase(TestCase):

    @classmethod
    def setUpClass(cls):
        super(ReportTestCase, cls).setUpClass()
        cls.domain = create_domain('test-domain')
        cls.web_user = WebUser.create('test-domain', 'test', 'test')

        SQLProduct.objects.create(
            domain=cls.domain.name,
            name='Product 2',
            code='p2',
            product_id='p2'
        )

        SQLProduct.objects.create(
            domain=cls.domain.name,
            name='Product 3',
            code='p3',
            product_id='p3'
        )

        SQLProduct.objects.create(
            domain=cls.domain.name,
            name='Product 1',
            code='p1',
            product_id='p1'
        )

        region_location_type = LocationType.objects.create(
            domain=cls.domain.name,
            name='Region',
        )

        SQLLocation.objects.create(
            domain=cls.domain.name,
            name='Region 1',
            location_id='r1',
            location_type=region_location_type
        )

        district_location_type = LocationType.objects.create(
            domain=cls.domain.name,
            name='District',
        )

        SQLLocation.objects.create(
            domain=cls.domain.name,
            name='District 1',
            location_id='d1',
            location_type=district_location_type
        )

        cls.engine = connection_manager.get_engine('default')
        cls.intra_table = IntraHealthFluff._table
        cls.couverture_table = CouvertureFluff._table
        cls.taux_table = TauxDeRuptureFluff._table
        cls.taux_de_satisfaction_table = TauxDeSatisfactionFluff._table
        cls.livraison_table = LivraisonFluff._table
        cls.recouvrement_table = RecouvrementFluff._table

        with cls.engine.begin() as connection:
            cls.couverture_table.create(connection, checkfirst=True)
            cls.intra_table.create(connection, checkfirst=True)
            cls.taux_table.create(connection, checkfirst=True)
            cls.taux_de_satisfaction_table.create(connection, checkfirst=True)
            cls.recouvrement_table.create(connection, checkfirst=True)
            cls.livraison_table.create(connection, checkfirst=True)

            insert = cls.intra_table.insert().values([
                dict(
                    doc_id='1',
                    date=datetime(2017, 11, 17),
                    product_name='Product 1',
                    product_id='p1',
                    district_id='d1',
                    district_name='District 1',
                    location_id='pps1',
                    region_id='r1',
                    PPS_name='PPS 1',
                    actual_consumption_total=10,
                    billed_consumption_total=5,
                    stock_total=33,
                    total_stock_total=70,
                    quantity_total=13,
                    cmm_total=16
                ),
                dict(
                    doc_id='1',
                    date=datetime(2017, 11, 17),
                    product_name='Product 2',
                    product_id='p2',
                    district_id='d1',
                    district_name='District 1',
                    location_id='pps1',
                    region_id='r1',
                    PPS_name='PPS 1',
                    actual_consumption_total=2,
                    billed_consumption_total=2,
                    stock_total=1,
                    total_stock_total=2,
                    quantity_total=3,
                    cmm_total=4
                ),
                dict(
                    doc_id='1',
                    date=datetime(2017, 11, 17),
                    product_name='Product 3',
                    product_id='p3',
                    district_id='d1',
                    district_name='District 1',
                    location_id='pps1',
                    region_id='r1',
                    PPS_name='PPS 1',
                    actual_consumption_total=6,
                    billed_consumption_total=4,
                    stock_total=14,
                    total_stock_total=0,
                    quantity_total=88,
                    cmm_total=99
                ),
                dict(
                    doc_id='2',
                    date=datetime(2017, 11, 17),
                    product_name='Product 1',
                    product_id='p1',
                    district_id='d1',
                    district_name='District 1',
                    location_id='pps2',
                    region_id='r1',
                    PPS_name='PPS 2',
                    actual_consumption_total=13,
                    billed_consumption_total=11,
                    stock_total=50,
                    total_stock_total=100,
                    quantity_total=1,
                    cmm_total=8
                ),
                dict(
                    doc_id='2',
                    date=datetime(2017, 11, 17),
                    product_name='Product 2',
                    product_id='p2',
                    district_id='d1',
                    district_name='District 1',
                    location_id='pps2',
                    region_id='r1',
                    PPS_name='PPS 2',
                    actual_consumption_total=0,
                    billed_consumption_total=0,
                    stock_total=2,
                    total_stock_total=17,
                    quantity_total=3,
                    cmm_total=15
                ),
                dict(
                    doc_id='2',
                    date=datetime(2017, 11, 17),
                    product_name='Product 3',
                    product_id='p3',
                    district_id='d1',
                    district_name='District 1',
                    location_id='pps2',
                    region_id='r1',
                    PPS_name='PPS 2',
                    actual_consumption_total=150,
                    billed_consumption_total=11,
                    stock_total=4,
                    total_stock_total=0,
                    quantity_total=11,
                    cmm_total=12
                )
            ])
            connection.execute(insert)

    @classmethod
    def tearDownClass(cls):
        with cls.engine.begin() as connection:
            cls.couverture_table.drop(connection, checkfirst=True)
            cls.intra_table.drop(connection, checkfirst=True)
            cls.taux_table.drop(connection, checkfirst=True)
            cls.taux_de_satisfaction_table.drop(connection, checkfirst=True)
            cls.recouvrement_table.drop(connection, checkfirst=True)
            cls.livraison_table.drop(connection, checkfirst=True)
        cls.engine.dispose()
        cls.web_user.delete()
        cls.domain.delete()
        super(ReportTestCase, cls).tearDownClass()
