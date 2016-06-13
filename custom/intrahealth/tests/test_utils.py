# coding=utf-8
from django.test.testcases import TestCase

from django.conf import settings
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.locations.models import LocationType, Location
from corehq.apps.products.models import Product
from corehq.apps.sms.tests.update_location_keyword_test import create_mobile_worker
from corehq.sql_db.connections import connection_manager

TEST_DOMAIN = 'testing-ipm-senegal'


class IntraHealthTestCase(TestCase):

    @classmethod
    def setUpClass(cls):
        super(IntraHealthTestCase, cls).setUpClass()
        cls.session_helper = connection_manager.get_session_helper(settings.SQL_REPORTING_DATABASE_URL)
        cls.engine = cls.session_helper.engine

        cls.domain = create_domain(TEST_DOMAIN)
        cls.region_type = LocationType.objects.create(domain=TEST_DOMAIN, name=u'Région')
        cls.district_type = LocationType.objects.create(domain=TEST_DOMAIN, name=u'District')
        cls.pps_type = LocationType.objects.create(domain=TEST_DOMAIN, name=u'PPS')

        cls.region = Location(domain=TEST_DOMAIN, name='Test region', location_type=u'Région')
        cls.region.save()
        cls.district = Location(
            domain=TEST_DOMAIN, name='Test district', location_type=u'District', parent=cls.region
        )
        cls.district.save()
        cls.pps = Location(domain=TEST_DOMAIN, name='Test PPS', location_type=u'PPS', parent=cls.district)
        cls.pps.save()

        cls.mobile_worker = create_mobile_worker(
            domain=TEST_DOMAIN, username='dummy', password='dummy', phone_number='777777'
        )
        cls.mobile_worker.location_id = cls.pps.get_id
        cls.mobile_worker.save()

        cls.product = Product(_id=u'81457658bdedd663f8b0bdadb19d8f22', name=u'ASAQ Nourisson', domain=TEST_DOMAIN)
        cls.product2 = Product(
            _id=u'81457658bdedd663f8b0bdadb19d83d8', name=u'ASAQ Petit Enfant', domain=TEST_DOMAIN
        )

        cls.product.save()
        cls.product2.save()

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()
        cls.region.delete()
        cls.district.delete()
        cls.pps.delete()
        cls.region_type.delete()
        cls.district_type.delete()
        cls.pps_type.delete()
        cls.domain.delete()
        super(IntraHealthTestCase, cls).tearDownClass()
