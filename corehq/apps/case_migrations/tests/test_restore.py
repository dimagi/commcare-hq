import uuid

from django.conf import settings
from django.test import TestCase
from django.urls import reverse

from casexml.apps.case.const import CASE_INDEX_CHILD
from casexml.apps.case.mock import CaseFactory, CaseIndex, CaseStructure

from corehq.apps.app_manager.tests.util import TestXmlMixin
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.locations.models import LocationType, SQLLocation
from corehq.apps.users.dbaccessors import delete_all_users
from corehq.apps.users.models import WebUser
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.util.hmac_request import get_hmac_digest
from corehq.util.test_utils import flag_enabled

from ..views import get_case_hierarchy_for_restore


class TestRelatedCases(TestCase, TestXmlMixin):
    domain = 'related-cases-domain'

    @classmethod
    def setUpClass(cls):
        super(TestRelatedCases, cls).setUpClass()
        cls.factory = CaseFactory(domain=cls.domain)

        cls.greatgranddad = cls._case_structure('Ymir', None, 'granddad')
        cls.granddad = cls._case_structure('Laufey', cls.greatgranddad, 'granddad')
        cls.dad = cls._case_structure('Loki', cls.granddad, 'dad')
        cls.kid = cls._case_structure('Sleipner', cls.dad, 'kid')
        cls.kid2 = cls._case_structure('Jormungandr', cls.dad, 'kid')
        cls.grandkid = cls._case_structure('Svadilfari', cls.kid, 'kid')

        cls.other_granddad = cls._case_structure('Odin', None, 'granddad')
        cls.other_dad = cls._case_structure('Thor', cls.other_granddad, 'dad')

        cls.factory.create_or_update_cases([cls.grandkid, cls.kid2, cls.other_dad])

    @staticmethod
    def _case_structure(name, parent, case_type):
        if parent:
            indices = [CaseIndex(
                parent,
                identifier='parent',
                relationship=CASE_INDEX_CHILD,
                related_type=parent.attrs['case_type'],
            )]
        else:
            indices = []
        return CaseStructure(
            case_id=uuid.uuid4().hex,
            attrs={
                "case_type": case_type,
                "create": True,
                "update": {"name": name},
            },
            indices=indices,
            walk_related=True,
        )

    def test_get_related_case_ids(self):
        dad_case = CaseAccessors(self.domain).get_case(self.dad.case_id)
        related_cases = get_case_hierarchy_for_restore(dad_case)
        # cases "above" this one should not be included
        self.assertItemsEqual(
            [c.case_id for c in related_cases],
            [self.dad.case_id, self.kid.case_id, self.kid2.case_id,
             self.grandkid.case_id]
        )

    @flag_enabled('ADD_LIMITED_FIXTURES_TO_CASE_RESTORE')
    def test_locations_in_restore(self):
        case_id = self.dad.case_id

        domain_obj = create_domain(self.domain)
        user = WebUser.create(self.domain, 'test-user', 'passmein', created_by=None, created_via=None)

        self.addCleanup(delete_all_users)
        self.addCleanup(domain_obj.delete)

        location_type = LocationType.objects.create(domain=self.domain, name="Top", code="top")
        location = SQLLocation.objects.create(domain=self.domain, name="Top Location", location_type=location_type)

        # a location in different domain that should not be present
        create_domain("random-domain")
        another_location_type = LocationType.objects.create(domain="random-domain", name="Top", code="top")
        SQLLocation.objects.create(domain="random-domain", name="Top Location",
                                   location_type=another_location_type)

        response = self._generate_restore(case_id, user)
        self.assertEqual(response.status_code, 200)

        response_content = next(response.streaming_content)

        locations_content = location_fixture_content.format(
            user_id=case_id,
            location_id=location.location_id
        )
        self.assertXmlPartialEqual(schema_fixture_content, response_content,
                                   '{http://openrosa.org/http/response}schema')
        self.assertXmlPartialEqual(locations_content, response_content,
                                   '{http://openrosa.org/http/response}fixture[@id="locations"]')

    def _generate_restore(self, case_id, user):
        self.client.login(username=user.username, password=user.password)
        url = reverse("migration_restore", args=[self.domain, case_id])
        hmac_header_value = get_hmac_digest(settings.FORMPLAYER_INTERNAL_AUTH_KEY, url)
        return self.client.get(url, HTTP_X_MAC_DIGEST=hmac_header_value)


schema_fixture_content = """
<partial>
    <ns0:schema xmlns:ns0="http://openrosa.org/http/response" id="locations">
        <ns0:indices>
            <ns0:index>@id</ns0:index>
            <ns0:index>@top_id</ns0:index>
            <ns0:index>@type</ns0:index>
            <ns0:index>name</ns0:index>
        </ns0:indices>
    </ns0:schema>
</partial>
"""


location_fixture_content = """
<partial>
    <ns0:fixture xmlns:ns0="http://openrosa.org/http/response" id="locations" indexed="true" user_id="{user_id}">
        <ns0:locations>
            <ns0:location id="{location_id}" top_id="{location_id}" type="top">
                <ns0:name>Top Location</ns0:name>
                <ns0:site_code>top_location</ns0:site_code>
                <ns0:external_id/>
                <ns0:latitude/>
                <ns0:longitude/>
                <ns0:location_type>Top</ns0:location_type>
                <ns0:supply_point_id/>
                <ns0:location_data/>
            </ns0:location>
        </ns0:locations>
    </ns0:fixture>
</partial>
"""
