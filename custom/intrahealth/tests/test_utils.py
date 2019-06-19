# coding=utf-8
from __future__ import absolute_import
from __future__ import unicode_literals
from django.test.testcases import TestCase

from casexml.apps.case.tests.util import delete_all_xforms
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.locations.models import LocationType, make_location
from corehq.apps.products.models import Product
from corehq.apps.users.models import CommCareUser
from corehq.sql_db.connections import connection_manager
from custom.intrahealth.models import (
    RecapPassageFluff,
    IntraHealthFluff,
    TauxDeRuptureFluff,
    LivraisonFluff,
    TauxDeSatisfactionFluff,
    CouvertureFluff,
)


TEST_DOMAIN = 'testing-ipm-senegal'


class IntraHealthTestCase(TestCase):

    @classmethod
    def setUpClass(cls):
        super(IntraHealthTestCase, cls).setUpClass()
        cls.engine = connection_manager.get_engine('default')

        cls.domain = create_domain(TEST_DOMAIN)
        cls.region_type = LocationType.objects.create(domain=TEST_DOMAIN, name='Région')
        cls.district_type = LocationType.objects.create(domain=TEST_DOMAIN, name='District')
        cls.pps_type = LocationType.objects.create(domain=TEST_DOMAIN, name='PPS')

        cls.region = make_location(domain=TEST_DOMAIN, name='Test region', location_type='Région')
        cls.region.save()
        cls.district = make_location(
            domain=TEST_DOMAIN, name='Test district', location_type='District', parent=cls.region
        )
        cls.district.save()
        cls.pps = make_location(domain=TEST_DOMAIN, name='Test PPS', location_type='PPS', parent=cls.district)
        cls.pps.save()

        cls.mobile_worker = CommCareUser.create(
            domain=TEST_DOMAIN, username='dummy', password='dummy', phone_number='777777'
        )
        cls.mobile_worker.location_id = cls.pps.get_id
        cls.mobile_worker.save()

        cls.product = Product(_id='81457658bdedd663f8b0bdadb19d8f22', name='ASAQ Nourisson', domain=TEST_DOMAIN)
        cls.product2 = Product(
            _id='81457658bdedd663f8b0bdadb19d83d8', name='ASAQ Petit Enfant', domain=TEST_DOMAIN
        )

        cls.product.save()
        cls.product2.save()

        cls.recap_table = RecapPassageFluff._table
        cls.intra_table = IntraHealthFluff._table
        cls.taux_rupt_table = TauxDeRuptureFluff._table
        cls.livraison_table = LivraisonFluff._table
        cls.taux_sat_table = TauxDeSatisfactionFluff._table
        cls.couverture_table = CouvertureFluff._table
        with cls.engine.begin() as connection:
            cls.recap_table.create(connection, checkfirst=True)
            cls.intra_table.create(connection, checkfirst=True)
            cls.taux_rupt_table.create(connection, checkfirst=True)
            cls.livraison_table.create(connection, checkfirst=True)
            cls.taux_sat_table.create(connection, checkfirst=True)
            cls.couverture_table.create(connection, checkfirst=True)

    @classmethod
    def tearDownClass(cls):
        with cls.engine.begin() as connection:
            cls.recap_table.drop(connection, checkfirst=True)
            cls.intra_table.drop(connection, checkfirst=True)
            cls.taux_rupt_table.drop(connection, checkfirst=True)
            cls.livraison_table.drop(connection, checkfirst=True)
            cls.taux_sat_table.drop(connection, checkfirst=True)
            cls.couverture_table.drop(connection, checkfirst=True)

        cls.engine.dispose()
        cls.mobile_worker.delete()
        cls.domain.delete()
        delete_all_xforms()
        super(IntraHealthTestCase, cls).tearDownClass()
