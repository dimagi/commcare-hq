from __future__ import absolute_import
from collections import Counter

from django.http.response import JsonResponse
from django.utils.decorators import method_decorator
from django.shortcuts import render
from django.views.generic.base import View, TemplateView

from dimagi.utils.couch.database import iter_docs

from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.domain.decorators import domain_admin_required
from corehq.apps.locations.permissions import location_safe
from corehq.apps.users.models import CommCareUser
from corehq.apps.userreports.reports.filters.choice_providers import ChoiceQueryContext, LocationChoiceProvider
from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from custom.enikshay.case_utils import CASE_TYPE_VOUCHER, CASE_TYPE_PERSON
from custom.enikshay.const import VOUCHER_ID, ENIKSHAY_ID
from custom.enikshay.reports.utils import StubReport
from custom.enikshay.reports.choice_providers import DistrictChoiceProvider
import six


@location_safe
class LocationsView(View):
    choice_provider = LocationChoiceProvider

    @method_decorator(login_and_domain_required)
    def dispatch(self, *args, **kwargs):
        return super(LocationsView, self).dispatch(*args, **kwargs)

    def get(self, request, domain, *args, **kwargs):
        user = self.request.couch_user

        query_context = ChoiceQueryContext(
            query=request.GET.get('q', None),
            limit=int(request.GET.get('limit', 20)),
            page=int(request.GET.get('page', 1)) - 1,
            user=user
        )
        location_choice_provider = self.choice_provider(StubReport(domain=domain), None)
        location_choice_provider.configure({
            'include_descendants': True,
            'order_by_hierarchy': True,
            'show_full_path': True,
        })
        return JsonResponse(
            {
                'results': [
                    {'id': location.value, 'text': location.display}
                    for location in location_choice_provider.query(query_context)
                ],
                'total': location_choice_provider.query_count(query_context.query, user)
            }
        )


@location_safe
class DistrictLocationsView(LocationsView):
    choice_provider = DistrictChoiceProvider


class DuplicateIdsReport(TemplateView):
    @method_decorator(domain_admin_required)
    def dispatch(self, *args, **kwargs):
        return super(DuplicateIdsReport, self).dispatch(*args, **kwargs)

    def get(self, request, domain, case_type, *args, **kwargs):
        self.case_type = {'voucher': CASE_TYPE_VOUCHER, 'person': CASE_TYPE_PERSON}[case_type]
        self.accessor = CaseAccessors(domain)
        case_ids = self.accessor.get_case_ids_in_domain(self.case_type)
        bad_cases = self.get_cases_with_duplicate_ids(case_ids)

        for case in bad_cases:
            form = CaseAccessorSQL.get_transactions(case['case_id'])[0].form
            if form:
                case['form_name'] = form.form_data.get('@name', 'NA')
                form_device_number = form.form_data.get('serial_id', {}).get('outputs', {}).get('device_number')
                case['device_number_in_form'] = form_device_number
                case['form_device_id'] = form.metadata.deviceID
                case['form_user_id'] = form.user_id
                case['auth_user_id'] = form.auth_context.get('user_id')

        self.add_user_info_to_cases(bad_cases)
        context = {
            'case_type': self.case_type,
            'num_bad_cases': len(bad_cases),
            'num_total_cases': len(case_ids),
            'num_good_cases': len(case_ids) - len(bad_cases),
            'bad_cases': sorted(bad_cases, key=lambda case: case['opened_on'], reverse=True)
        }
        return render(request, 'enikshay/duplicate_ids_report.html', context)

    def add_user_info_to_cases(self, bad_cases):
        user_info = self.get_user_info(
            case['form_user_id'] for case in bad_cases if 'form_user_id' in case)

        auth_user_ids = [case['auth_user_id'] for case in bad_cases
                         if 'auth_user_id' in case]
        auth_usernames = {user_doc['_id']: user_doc['username'] for user_doc in
                          iter_docs(CommCareUser.get_db(), auth_user_ids)}
        for case in bad_cases:
            user_dict = user_info.get(case.get('form_user_id'))
            if user_dict:
                case['username'] = user_dict['username']
                device_id = case['form_device_id']
                if device_id == 'Formplayer':
                    if case['form_user_id'] == case['auth_user_id']:
                        device_id = "WebAppsLogin"
                    else:
                        auth_username = auth_usernames.get(case['auth_user_id'])
                        device_id = "WebAppsLogin*{}*as*{}".format(
                            auth_username, user_dict['username']).replace('.', '_')
                try:
                    device_number = user_dict['device_ids'].index(device_id) + 1
                except ValueError:
                    device_number = -1
                case['real_device_number'] = six.text_type(device_number)

    def get_cases_with_duplicate_ids(self, all_case_ids):
        id_property = {'voucher': VOUCHER_ID, 'person': ENIKSHAY_ID}[self.case_type]
        all_cases = [
            {
                'case_id': case.case_id,
                'readable_id': case.get_case_property(id_property),
                'opened_on': case.opened_on,
            }
            for case in self.accessor.iter_cases(all_case_ids)
        ]
        counts = Counter(case['readable_id'] for case in all_cases)
        return [case for case in all_cases if counts[case['readable_id']] > 1]

    def get_user_info(self, user_ids):
        return {
            user_doc['_id']: {
                'username': user_doc['username'].split('@')[0],
                'device_ids': [d['device_id'] for d in user_doc['devices']],
            }
            for user_doc in iter_docs(CommCareUser.get_db(), user_ids)
        }
