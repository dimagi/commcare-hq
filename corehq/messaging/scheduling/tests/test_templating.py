from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.domain.models import Domain
from corehq.apps.groups.models import Group
from corehq.apps.locations.models import SQLLocation, LocationType
from corehq.apps.users.models import CommCareUser, WebUser
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.tests.utils import run_with_all_backends
from corehq.messaging.templating import MessagingTemplateRenderer, CaseMessagingTemplateParam
from corehq.util.test_utils import create_test_case, set_parent_case
from django.test import TestCase


class TemplatingTestCase(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TemplatingTestCase, cls).setUpClass()

        cls.domain = 'templating-test'
        cls.domain_obj = Domain(name=cls.domain)
        cls.domain_obj.save()

        cls.mobile_user = CommCareUser.create(
            cls.domain,
            'mobile1@templating-test',
            '12345',
            first_name='Mobile',
            last_name='User'
        )
        cls.mobile_user.add_phone_number('999123')
        cls.mobile_user.save()

        cls.web_user = WebUser.create(
            cls.domain,
            'web1@templating-test',
            '12345',
            first_name='Web',
            last_name='User'
        )
        cls.web_user.add_phone_number('999456')
        cls.web_user.save()

        cls.group = Group(domain=cls.domain, name='Test Group')
        cls.group.save()

        cls.location_type = LocationType.objects.create(
            domain=cls.domain,
            name='top-level',
            code='top-level'
        )

        cls.location = SQLLocation.objects.create(
            domain=cls.domain,
            name='Test Location',
            site_code='loc1234',
            location_type=cls.location_type
        )

    @classmethod
    def tearDownClass(cls):
        cls.mobile_user.delete()
        cls.web_user.delete()
        cls.group.delete()
        cls.location.delete()
        cls.location_type.delete()
        cls.domain_obj.delete()
        super(TemplatingTestCase, cls).tearDownClass()

    def create_child_case(self, owner=None, modified_by=None):
        owner = owner or self.mobile_user
        modified_by = modified_by or self.mobile_user
        return create_test_case(self.domain, 'child', 'P002',
            case_properties={'child_prop1': 'def', 'unicode_property': '\u0928\u092e\u0938\u094d\u0924\u0947'},
            owner_id=owner.get_id, user_id=modified_by.get_id)

    def create_parent_case(self, owner=None, modified_by=None):
        owner = owner or self.mobile_user
        modified_by = modified_by or self.mobile_user
        return create_test_case(self.domain, 'parent', 'P001', case_properties={'parent_prop1': 'abc'},
            owner_id=owner.get_id, user_id=modified_by.get_id)

    @run_with_all_backends
    def test_case_template_params(self):
        with self.create_child_case() as case:
            r = MessagingTemplateRenderer()
            r.set_context_param('case', CaseMessagingTemplateParam(case))

            self.assertEqual(
                r.render("No template variables"),
                "No template variables"
            )
            self.assertEqual(
                r.render("Case's name is {case.name}"),
                "Case's name is P002"
            )
            self.assertEqual(
                r.render("Multiple properties: {case.name}, {case.child_prop1}"),
                "Multiple properties: P002, def"
            )
            self.assertEqual(
                r.render("Unicode property: {case.unicode_property}"),
                "Unicode property: \u0928\u092e\u0938\u094d\u0924\u0947"
            )
            self.assertEqual(
                r.render("Don't render case: {case}"),
                "Don't render case: (?)"
            )
            self.assertEqual(
                r.render("Unknown property: {case.unknown}"),
                "Unknown property: (?)"
            )
            self.assertEqual(
                r.render("Unknown property: {case.unknown.unknown}"),
                "Unknown property: (?)"
            )
            self.assertEqual(
                r.render("Unknown param: {x}"),
                "Unknown param: (?)"
            )

    @run_with_all_backends
    def test_parent_case_template_params(self):
        with self.create_child_case() as child_case, self.create_parent_case() as parent_case:
            set_parent_case(self.domain, child_case, parent_case)
            child_case = CaseAccessors(self.domain).get_case(child_case.case_id)

            r = MessagingTemplateRenderer()
            r.set_context_param('case', CaseMessagingTemplateParam(child_case))

            self.assertEqual(
                r.render("Child case prop: {case.child_prop1}"),
                "Child case prop: def"
            )
            self.assertEqual(
                r.render("Parent case prop: {case.parent.parent_prop1}"),
                "Parent case prop: abc"
            )
            self.assertEqual(
                r.render("Don't render case: {case.parent}"),
                "Don't render case: (?)"
            )
            self.assertEqual(
                r.render("No grandparent case: {case.parent.parent.name}"),
                "No grandparent case: (?)"
            )
            self.assertEqual(
                r.render("No host case: {case.host.name}"),
                "No host case: (?)"
            )

    @run_with_all_backends
    def test_host_case_template_params(self):
        with self.create_child_case() as extension_case, self.create_parent_case() as host_case:
            set_parent_case(self.domain, extension_case, host_case, relationship='extension')
            extension_case = CaseAccessors(self.domain).get_case(extension_case.case_id)

            r = MessagingTemplateRenderer()
            r.set_context_param('case', CaseMessagingTemplateParam(extension_case))

            self.assertEqual(
                r.render("Extension case prop: {case.child_prop1}"),
                "Extension case prop: def"
            )
            self.assertEqual(
                r.render("Host case prop: {case.host.parent_prop1}"),
                "Host case prop: abc"
            )
            self.assertEqual(
                r.render("Don't render case: {case.host}"),
                "Don't render case: (?)"
            )
            self.assertEqual(
                r.render("No host host case: {case.host.host.name}"),
                "No host host case: (?)"
            )
            self.assertEqual(
                r.render("No parent case: {case.parent.name}"),
                "No parent case: (?)"
            )

    @run_with_all_backends
    def test_owner_template_params(self):
        r = MessagingTemplateRenderer()

        with self.create_parent_case(owner=self.mobile_user) as case:
            r.set_context_param('case', CaseMessagingTemplateParam(case))
            self.assertEqual(r.render("Name: {case.owner.name}"), "Name: mobile1")
            self.assertEqual(r.render("First Name: {case.owner.first_name}"), "First Name: Mobile")
            self.assertEqual(r.render("Last Name: {case.owner.last_name}"), "Last Name: User")
            self.assertEqual(r.render("Phone: {case.owner.phone_number}"), "Phone: 999123")
            self.assertEqual(r.render("Unknown: {case.owner.unknown}"), "Unknown: (?)")
            self.assertEqual(r.render("Unknown: {case.owner.unknown.unknown}"), "Unknown: (?)")

        with self.create_parent_case(owner=self.web_user) as case:
            r.set_context_param('case', CaseMessagingTemplateParam(case))
            self.assertEqual(r.render("Name: {case.owner.name}"), "Name: web1@templating-test")
            self.assertEqual(r.render("First Name: {case.owner.first_name}"), "First Name: Web")
            self.assertEqual(r.render("Last Name: {case.owner.last_name}"), "Last Name: User")
            self.assertEqual(r.render("Phone: {case.owner.phone_number}"), "Phone: 999456")
            self.assertEqual(r.render("Unknown: {case.owner.unknown}"), "Unknown: (?)")
            self.assertEqual(r.render("Unknown: {case.owner.unknown.unknown}"), "Unknown: (?)")

        with self.create_parent_case(owner=self.group) as case:
            r.set_context_param('case', CaseMessagingTemplateParam(case))
            self.assertEqual(r.render("Name: {case.owner.name}"), "Name: Test Group")
            self.assertEqual(r.render("Unknown: {case.owner.unknown}"), "Unknown: (?)")
            self.assertEqual(r.render("Unknown: {case.owner.unknown.unknown}"), "Unknown: (?)")

        with self.create_parent_case(owner=self.location) as case:
            r.set_context_param('case', CaseMessagingTemplateParam(case))
            self.assertEqual(r.render("Name: {case.owner.name}"), "Name: Test Location")
            self.assertEqual(r.render("Site Code: {case.owner.site_code}"), "Site Code: loc1234")
            self.assertEqual(r.render("Unknown: {case.owner.unknown}"), "Unknown: (?)")
            self.assertEqual(r.render("Unknown: {case.owner.unknown.unknown}"), "Unknown: (?)")

    @run_with_all_backends
    def test_modified_by_template_params(self):
        r = MessagingTemplateRenderer()

        with self.create_parent_case(modified_by=self.mobile_user) as case:
            r.set_context_param('case', CaseMessagingTemplateParam(case))
            self.assertEqual(r.render("Name: {case.last_modified_by.name}"), "Name: mobile1")
            self.assertEqual(r.render("First Name: {case.last_modified_by.first_name}"), "First Name: Mobile")
            self.assertEqual(r.render("Last Name: {case.last_modified_by.last_name}"), "Last Name: User")
            self.assertEqual(r.render("Phone: {case.last_modified_by.phone_number}"), "Phone: 999123")
            self.assertEqual(r.render("Unknown: {case.last_modified_by.unknown}"), "Unknown: (?)")
            self.assertEqual(r.render("Unknown: {case.last_modified_by.unknown.unknown}"), "Unknown: (?)")

        with self.create_parent_case(modified_by=self.web_user) as case:
            r.set_context_param('case', CaseMessagingTemplateParam(case))
            self.assertEqual(r.render("Name: {case.last_modified_by.name}"), "Name: web1@templating-test")
            self.assertEqual(r.render("First Name: {case.last_modified_by.first_name}"), "First Name: Web")
            self.assertEqual(r.render("Last Name: {case.last_modified_by.last_name}"), "Last Name: User")
            self.assertEqual(r.render("Phone: {case.last_modified_by.phone_number}"), "Phone: 999456")
            self.assertEqual(r.render("Unknown: {case.last_modified_by.unknown}"), "Unknown: (?)")
            self.assertEqual(r.render("Unknown: {case.last_modified_by.unknown.unknown}"), "Unknown: (?)")
