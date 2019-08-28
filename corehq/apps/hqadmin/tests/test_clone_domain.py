from django.test import TestCase

from mock import patch

from corehq.apps.domain.models import Domain
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.hqadmin.management.commands.clone_domain import \
    Command as CloneCommand
from corehq.apps.locations.models import LocationType, SQLLocation
from corehq.apps.locations.tests.util import setup_locations_and_types
from corehq.apps.users.dbaccessors.all_commcare_users import delete_all_users
from corehq.apps.users.models import CommCareUser, WebUser
from corehq.motech.repeaters.dbaccessors import delete_all_repeaters


class TestCloneDomain(TestCase):
    old_domain = "normal-world"
    new_domain = "the-upside-down"

    def setUp(self):
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

    def make_clone(self, include=None):
        options = {'settings': None, 'pythonpath': None, 'verbosity': 1,
                   'traceback': None, 'no_color': False, 'exclude': None,
                   'include': include, 'nocommit': False}
        with patch('corehq.apps.callcenter.data_source.get_call_center_domains', lambda: []):
            CloneCommand().handle(self.old_domain, self.new_domain, **options)
            return Domain.get_by_name(self.new_domain)

    def tearDown(self):
        self.old_domain_obj.delete()
        new_domain_obj = Domain.get_by_name(self.new_domain)
        if new_domain_obj:
            new_domain_obj.delete()
        delete_all_users()
        delete_all_repeaters()

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

        self.make_clone(include=['locations', 'location_types'])

        self.assertItemsEqual(
            location_types_snapshot(self.old_domain),
            location_types_snapshot(self.new_domain),
        )

        self.assertItemsEqual(
            locations_snapshot(self.old_domain),
            locations_snapshot(self.new_domain),
        )

        # Make sure parents and types are in the same domain
        for location in SQLLocation.objects.filter(domain__in=[self.old_domain, self.new_domain]):
            if location.parent is not None:
                self.assertEqual(location.domain, location.parent.domain)
            self.assertEqual(location.domain, location.location_type.domain)

        # Make sure the locations are only related to locations in the same domain
        for domain in (self.old_domain, self.new_domain):
            locs_in_domain = SQLLocation.objects.filter(domain=domain)
            related_to_other_domain = (
                SQLLocation.objects
                .get_queryset_ancestors(locs_in_domain)
                # exclude here instead of at end (on union queryset) because
                # django discards filters on union queries?? (django bug?)
                .exclude(domain=domain)
                .values("name")
                .order_by()  # discard ORDER BY
                .union(
                    SQLLocation.objects
                    .get_queryset_descendants(locs_in_domain)
                    .exclude(domain=domain)  # exclude here instead of at end...
                    .values("name")
                    .order_by(),  # discard ORDER BY
                    all=True,
                )
            )
            if related_to_other_domain.exists():
                self.assertTrue(False, repr(list(related_to_other_domain)))

    def test_clone_repeaters(self):
        from corehq.motech.repeaters.models import Repeater
        from corehq.motech.repeaters.models import CaseRepeater
        from corehq.motech.repeaters.models import FormRepeater

        self.assertEqual(0, len(Repeater.by_domain(self.new_domain)))

        case_repeater = CaseRepeater(
            domain=self.old_domain,
            url='case-repeater-url',
        )
        case_repeater.save()
        self.addCleanup(case_repeater.delete)
        form_repeater = FormRepeater(
            domain=self.old_domain,
            url='form-repeater-url',
        )
        form_repeater.save()
        self.addCleanup(form_repeater.delete)

        self.make_clone(include=['repeaters'])

        cloned_repeaters = Repeater.by_domain(self.new_domain)
        self.assertEqual(2, len(cloned_repeaters))
        self.assertEqual(
            {'CaseRepeater', 'FormRepeater'},
            {repeater.doc_type for repeater in cloned_repeaters}
        )
