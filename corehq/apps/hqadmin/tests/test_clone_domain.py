from django.test import TestCase
from mock import patch

from corehq.apps.domain.models import Domain
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.locations.models import SQLLocation, LocationType
from corehq.apps.locations.tests.util import setup_locations_and_types, delete_all_locations
from corehq.apps.users.dbaccessors.all_commcare_users import delete_all_users
from corehq.apps.users.models import CommCareUser, WebUser

from corehq.apps.hqadmin.management.commands.clone_domain import Command as CloneCommand


class TestCloneDomain(TestCase):
    old_domain = "normal-world"
    new_domain = "the-upside-down"

    def setUp(self):
        delete_all_users()
        delete_all_locations()
        self.old_domain_obj = create_domain(self.old_domain)
        self.mobile_worker = CommCareUser.create(self.old_domain, 'will@normal-world.commcarehq.org', '123')
        self.web_user = WebUser.create(self.old_domain, 'barb@hotmail.com', '***', is_active=True)
        self.location_types, self.locations = setup_locations_and_types(
            self.old_domain,
            location_types=["state", "county", "city"],
            stock_tracking_types=[],
            locations=[
                ('Massachusetts', [
                    ('Middlesex', [
                        ('Cambridge', []),
                        ('Somerville', []),
                    ]),
                    ('Suffolk', [
                        ('Boston', []),
                    ])
                ]),
                ('California', [
                    ('Los Angeles', []),
                ]),
            ]
        )

    def make_clone(self):
        options = {'settings': None, 'pythonpath': None, 'verbosity': 1,
                   'traceback': None, 'no_color': False, 'exclude': None,
                   'include': None, 'nocommit': False}
        with patch('corehq.apps.callcenter.data_source.get_call_center_domains', lambda: []):
            CloneCommand().handle(self.old_domain, self.new_domain, **options)
            return Domain.get_by_name(self.new_domain)

    def tearDown(self):
        self.old_domain_obj.delete()
        new_domain_obj = Domain.get_by_name(self.new_domain)
        if new_domain_obj:
            new_domain_obj.delete()
        delete_all_users()
        delete_all_locations()

    def test_same_locations(self):

        def location_types_snapshot(domain):
            return [
                (loc.code, loc.parent_type.code if loc.parent_type else None)
                for loc in LocationType.objects.filter(domain=domain)
            ]

        def locations_snapshot(domain):
            return [
                (loc.site_code, loc.parent.site_code if loc.parent else None)
                for loc in SQLLocation.active_objects.filter(domain=domain)
            ]

        self.make_clone()

        self.assertItemsEqual(
            location_types_snapshot(self.old_domain),
            location_types_snapshot(self.new_domain),
        )

        self.assertItemsEqual(
            locations_snapshot(self.old_domain),
            locations_snapshot(self.new_domain),
        )
