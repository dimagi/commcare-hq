from unittest.mock import patch

from django.test import TestCase
from django.test.client import RequestFactory

from corehq.apps.app_manager.app_schemas.case_properties import (
    all_case_properties_by_domain,
)
from corehq.apps.data_dictionary.models import CaseProperty, CaseType
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.es.cases import case_adapter
from corehq.apps.es.tests.utils import es_test
from corehq.apps.es.users import user_adapter
from corehq.apps.letters import reports as letter_reports
from corehq.apps.letters.models import LetterTemplate
from corehq.apps.letters.reports import LetterReport
from corehq.apps.users.models import DomainMembership, WebUser
from corehq.form_processor.tests.utils import create_case
from corehq.util.test_utils import flag_enabled

DOMAIN = 'letters-report'


@es_test(requires=[case_adapter], setup_class=True)
class TestLetterReport(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = WebUser(username='t@x.com', domains=[DOMAIN])
        cls.user.domain_memberships = [DomainMembership(domain=DOMAIN, role_id='admin')]
        client_type = CaseType.objects.create(domain=DOMAIN, name='client')
        for prop in ('tpl', 'district', 'name', 'parent/x'):
            CaseProperty.objects.create(case_type=client_type, name=prop)
        # Data dictionary properties are only read when the domain has the privilege
        privilege_patch = patch(
            'corehq.apps.app_manager.app_schemas.case_properties.domain_has_privilege',
            return_value=True,
        )
        privilege_patch.start()
        cls.addClassCleanup(privilege_patch.stop)
        all_case_properties_by_domain.clear(DOMAIN, True, True)
        cls.addClassCleanup(all_case_properties_by_domain.clear, DOMAIN, True, True)
        cls.tpl = LetterTemplate.objects.create(domain=DOMAIN, name='t', body='<p>Dear {{ case_name }}</p>')
        cls.foreign = LetterTemplate.objects.create(domain='elsewhere', name='f', body='FOREIGN')
        cases = [
            create_case(DOMAIN, case_type='client', name='Ana', save=True,
                        case_json={'tpl': str(cls.tpl.pk), 'district': 'North'}),
            create_case(DOMAIN, case_type='client', name='Bob', save=True,
                        case_json={'tpl': str(cls.foreign.pk)}),
            create_case(DOMAIN, case_type='other', name='Cy', save=True,
                        case_json={'tpl': str(cls.tpl.pk)}),
        ]
        case_adapter.bulk_index(cases, refresh=True)

    def _context(self, **params):
        request = RequestFactory().get('/', params)
        request.couch_user = self.user
        request.domain = DOMAIN
        request.can_access_all_locations = True
        return LetterReport(request, domain=DOMAIN).report_context

    def test_renders_selected_case_type_only_and_ignores_foreign_templates(self):
        ctx = self._context(case_type='client', template_property='tpl')
        assert [s.title for s in ctx['sections']] == [None]
        assert ctx['sections'][0].letters == ['<p>Dear Ana</p>']
        assert [s.case_name for s in ctx['skipped']] == ['Bob']

    def test_group_by(self):
        ctx = self._context(case_type='client', template_property='tpl', group_by='district')
        assert [str(s.title) for s in ctx['sections']] == ['North']

    def test_needs_case_type_and_template_property(self):
        assert self._context(case_type='client') == {'needs_filters': True}

    def test_unknown_template_property_rejected(self):
        assert self._context(case_type='client', template_property='not_a_prop') == {'needs_filters': True}

    def test_over_cap(self):
        with patch.object(letter_reports, 'MAX_LETTERS', 1):
            ctx = self._context(case_type='client', template_property='tpl')
        assert ctx == {'too_many': 1}

    def test_property_filter_options_exclude_parent_props(self):
        from corehq.apps.letters.filters import SortByFilter
        request = RequestFactory().get('/', {'case_type': 'client'})
        options = [value for value, _ in SortByFilter(request, DOMAIN).options]
        assert 'name' in options
        assert 'parent/x' not in options

    def test_sort_by_name_property(self):
        ctx = self._context(case_type='client', template_property='tpl', sort_by='name')
        assert ctx['sections'][0].letters == ['<p>Dear Ana</p>']


@es_test(requires=[case_adapter, user_adapter], setup_class=True)
@flag_enabled('LETTER_TEMPLATES')
class TestLetterReportView(TestCase):
    domain = 'letters-report-http'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(cls.domain)
        cls.addClassCleanup(cls.domain_obj.delete)
        cls.user = WebUser.create(cls.domain, 'admin@letters-http.com', 'pw', None, None, is_admin=True)
        cls.addClassCleanup(cls.user.delete, cls.domain, deleted_by=None)
        user_adapter.index(cls.user, refresh=True)
        CaseProperty.objects.create(
            case_type=CaseType.objects.create(domain=cls.domain, name='client'), name='tpl')
        privilege_patch = patch(
            'corehq.apps.app_manager.app_schemas.case_properties.domain_has_privilege',
            return_value=True,
        )
        privilege_patch.start()
        cls.addClassCleanup(privilege_patch.stop)
        all_case_properties_by_domain.clear(cls.domain, True, True)
        cls.addClassCleanup(all_case_properties_by_domain.clear, cls.domain, True, True)
        tpl = LetterTemplate.objects.create(domain=cls.domain, name='t', body='<p>Dear {{ case_name }}</p>')
        case = create_case(cls.domain, case_type='client', name='Ana', save=True,
                           case_json={'tpl': str(tpl.pk)})
        case_adapter.index(case, refresh=True)

    def test_async_report_renders_letters(self):
        self.client.login(username=self.user.username, password='pw')
        url = LetterReport.get_url(self.domain, render_as='async')
        response = self.client.get(url, {'case_type': 'client', 'template_property': 'tpl'})
        assert response.status_code == 200
        assert 'Dear Ana' in response.json()['report']
