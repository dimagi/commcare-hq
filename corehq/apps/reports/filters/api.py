"""
API endpoints for filter options
"""
import logging
import json
import uuid
from dataclasses import dataclass

from django.views.generic import View
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils.translation import gettext_lazy as _

from braces.views import JSONResponseMixin
from memoized import memoized

from casexml.apps.case.mock import CaseBlock
from corehq.apps.hqcase.utils import get_deidentified_data
from corehq.apps.users.util import SYSTEM_USER_ID
from corehq.form_processor.models import CommCareCase

from dimagi.utils.logging import notify_exception
from phonelog.models import DeviceReportEntry

from corehq.apps.case_importer.do_import import (
    RowAndCase,
    SubmitCaseBlockHandler,
)
from corehq.apps.domain.decorators import LoginAndDomainMixin
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import HqPermissions
from corehq.apps.locations.permissions import location_safe
from corehq.apps.reports.const import DEFAULT_PAGE_LIMIT
from corehq.apps.reports.filters.controllers import (
    CaseListFilterOptionsController,
    EmwfOptionsController,
    MobileWorkersOptionsController,
    ReassignCaseOptionsController,
    EnterpriseUserOptionsController,
)
from corehq.apps.users.analytics import get_search_users_in_domain_es_query
from corehq.elastic import ESError
from django_prbac.decorators import requires_privilege
from corehq import privileges, toggles
from corehq.apps.accounting.utils import domain_has_privilege

logger = logging.getLogger(__name__)


@location_safe
class EmwfOptionsView(LoginAndDomainMixin, JSONResponseMixin, View):
    """
    Paginated options for the ExpandedMobileWorkerFilter
    """

    @property
    @memoized
    def options_controller(self):
        return EmwfOptionsController(self.request, self.domain, self.search)

    def get(self, request, domain):
        self.domain = domain
        self.search = self.request.GET.get('q', '')

        try:
            count, options = self.options_controller.get_options()
            return self.render_json_response({
                'results': options,
                'total': count,
            })
        except ESError as e:
            if self.search:
                # Likely caused by an invalid user query
                # A query that causes this error immediately follows a very
                # similar query that should be caught by the else clause if it
                # errors.  If that error didn't happen, the error was probably
                # introduced by the addition of the query_string query, which
                # contains the user's input.
                logger.info('ElasticSearch error caused by query "%s": %s',
                            self.search, e)
            else:
                # The error was our fault
                notify_exception(request, e)
        return self.render_json_response({
            'results': [],
            'total': 0,
        })


class MobileWorkersOptionsView(EmwfOptionsView):
    """
    Paginated Options for the Mobile Workers selection tool
    """
    urlname = 'users_select2_options'

    @property
    @memoized
    def options_controller(self):
        return MobileWorkersOptionsController(self.request, self.domain, self.search)

    # This endpoint is used by select2 single option filters
    def post(self, request, domain):
        self.domain = domain
        self.search = self.request.POST.get('q', None)
        try:
            count, options = self.options_controller.get_options()
            return self.render_json_response({
                'items': options,
                'total': count,
                'limit': request.POST.get('page_limit', DEFAULT_PAGE_LIMIT),
                'success': True
            })
        except ESError as e:
            if self.search:
                # Likely caused by an invalid user query
                # A query that causes this error immediately follows a very
                # similar query that should be caught by the else clause if it
                # errors.  If that error didn't happen, the error was probably
                # introduced by the addition of the query_string query, which
                # contains the user's input.
                logger.info('ElasticSearch error caused by query "%s": %s',
                            self.search, e)
            else:
                # The error was our fault
                notify_exception(request, e)
        return self.render_json_response({
            'results': [],
            'total': 0,
        })


@location_safe
class CaseListFilterOptions(EmwfOptionsView):

    @property
    @memoized
    def options_controller(self):
        return CaseListFilterOptionsController(self.request, self.domain, self.search)


@location_safe
class CaseListActionOptions(CaseListFilterOptions):
    @property
    @memoized
    def options_controller(self):
        from corehq.apps.data_interfaces.interfaces import CaseCopyInterface
        if (
            self.request.GET.get('action') == CaseCopyInterface.action
            and domain_has_privilege(self.domain, privileges.CASE_COPY)
        ):
            return MobileWorkersOptionsController(self.request, self.domain, self.search)
        return ReassignCaseOptionsController(self.request, self.domain, self.search)


class EnterpriseUserOptions(EmwfOptionsView):
    """View designed to return all users across all enterprise domains when the request
    is made from the enterprise domain and the request is not location restricted.

    If either of those conditions are false then only users from the current domain are returned
    """
    @property
    @memoized
    def options_controller(self):
        return EnterpriseUserOptionsController(self.request, self.domain, self.search)


class DeviceLogFilter(LoginAndDomainMixin, JSONResponseMixin, View):
    field = None

    def get(self, request, domain):
        q = self.request.GET.get('q', None)
        field_filter = {self.field + "__startswith": q}
        query_set = (
            DeviceReportEntry.objects
            .filter(domain=domain)
            .filter(**field_filter)
            .distinct(self.field)
            .values_list(self.field, flat=True)
            .order_by(self.field)
        )
        values = query_set[self._offset():self._offset() + self._page_limit() + 1]
        return self.render_json_response({
            'results': [{'id': v, 'text': v} for v in values[:self._page_limit()]],
            'pagination': {
                'more': len(values) > self._page_limit(),
            },
        })

    def _page_limit(self):
        page_limit = self.request.GET.get("page_limit", DEFAULT_PAGE_LIMIT)
        try:
            return int(page_limit)
        except ValueError:
            return DEFAULT_PAGE_LIMIT

    def _page(self):
        page = self.request.GET.get("page", 1)
        try:
            return int(page)
        except ValueError:
            return 1

    def _offset(self):
        return self._page_limit() * (self._page() - 1)


class DeviceLogUsers(DeviceLogFilter):

    def get(self, request, domain):
        q = self.request.GET.get('q', None)
        users_query = (get_search_users_in_domain_es_query(domain, q, self._page_limit(), self._offset())
            .show_inactive()
            .remove_default_filter("not_deleted")
            .source("username")
        )
        values = [x['username'].split("@")[0] for x in users_query.run().hits]
        count = users_query.count()
        return self.render_json_response({
            'results': [{'id': v, 'text': v} for v in values],
            'total': count,
        })


class DeviceLogIds(DeviceLogFilter):
    field = 'device_id'


@require_POST
@toggles.COPY_CASES.required_decorator()
@require_permission(HqPermissions.edit_data)
@requires_privilege(privileges.CASE_COPY)
@location_safe
def copy_cases(request, domain, *args, **kwargs):
    body = json.loads(request.body)

    case_ids = body.get('case_ids')
    if not case_ids:
        return JsonResponse({'error': _("Missing case ids")}, status=400)

    new_owner = body.get('owner_id')
    if not new_owner:
        return JsonResponse({'error': _("Missing new owner id")}, status=400)

    censor_data = {
        prop['name']: prop['label']
        for prop in body.get('sensitive_properties', [])
    }

    case_id_pairs, errors = _copy_cases(
        domain=domain,
        case_ids=case_ids,
        to_owner=new_owner,
        censor_data=censor_data,
    )
    count = len(case_id_pairs)
    return JsonResponse(
        {'copied_cases': count, 'error': errors},
        status=400 if count == 0 else 200,
    )


def _copy_cases(
    domain,
    case_ids,
    to_owner,
    censor_data=None,
):
    """
    Copies the cases governed by ``case_ids`` to the respective
    ``to_owner`` and replacing the relevant case properties with the
    specified 'replace_props' on the copied cases (useful for hiding
    sensitive data).

    :param domain: the domain string
    :param case_ids: case ids of the cases to copy
    :param to_owner: the owner to copy the cases to
    :param censor_data: the attributes/properties to be censored,
        specified as a dict. The keys corresponding to the
        property/attribute and the value specifies the type of censored
        data, i.e. number or date
    :returns: A list of original- and new case ID pairs and a list of
        errors encountered.
    """

    if not to_owner:
        return [], [_('Must copy cases to valid new owner')]

    original_cases = CommCareCase.objects.get_cases(case_ids, domain)
    if not original_cases:
        return [], []

    @dataclass
    class UserDuck:
        """Quacks like a User"""
        user_id: str
        username: str

    system_user = UserDuck(user_id=SYSTEM_USER_ID, username='system')
    submission_handler = SubmitCaseBlockHandler(
        domain,
        import_results=None,
        case_type=None,
        user=system_user,
        record_form_callback=None,
        throttle=True,
        add_inferred_props_to_schema=False,
    )

    processed_cases = {}

    def _get_new_identifier_index(case_identifier_index):
        _identifier_index = {**case_identifier_index}
        original_referenced_id = _identifier_index['case_id']

        # We need the copied case's case_id for the new index
        if original_referenced_id in processed_cases:
            _identifier_index['case_id'] = processed_cases[original_referenced_id].case_id
        else:
            # Need to process the referenced case first to get the case_id of the copied case
            try:
                original_parent_case = next(
                    orig_case for orig_case in original_cases
                    if orig_case.case_id == original_referenced_id
                )
            except StopIteration:
                return {}
            if original_parent_case.case_id not in processed_cases:
                referenced_caseblock = _create_caseblock(original_parent_case)
                processed_cases[original_parent_case.case_id] = referenced_caseblock
                _identifier_index['case_id'] = referenced_caseblock.case_id
        return (
            _identifier_index['case_type'],
            _identifier_index['case_id'],
            _identifier_index['relationship'],
        )

    def _get_new_index_map(_case):
        new_case_index = {}
        index_map = _case.get_index_map()
        for identifier, index_dict in index_map.items():
            identifier_index = _get_new_identifier_index(index_dict)
            if identifier_index:
                new_case_index[identifier] = identifier_index
        return new_case_index

    def _create_caseblock(_case):
        deid_attrs, deid_props = get_deidentified_data(_case, censor_data)
        case_name = deid_attrs.get('case_name') or deid_attrs.get('name')
        return CaseBlock(
            create=True,
            case_id=uuid.uuid4().hex,
            owner_id=to_owner,
            case_name=case_name or _case.name,
            case_type=_case.type,
            update={**_case.case_json, **deid_props},
            index=_get_new_index_map(_case),
            external_id=deid_attrs.get('external_id', _case.external_id),
            date_opened=deid_attrs.get('date_opened', _case.opened_on),
            user_id=SYSTEM_USER_ID,
        )

    errors = []
    for i, orig_case in enumerate(original_cases):
        if orig_case.owner_id == to_owner:
            errors.append(_(
                'Original case owner {owner_id} cannot copy case '
                '{case_id} to themselves.'
            ).format(
                owner_id=orig_case.owner_id,
                case_id=orig_case.case_id,
            ))
            continue
        if orig_case.case_id not in processed_cases:
            caseblock = _create_caseblock(orig_case)
            processed_cases[orig_case.case_id] = caseblock
            submission_handler.add_caseblock(RowAndCase(row=i, case=caseblock))
    submission_handler.commit_caseblocks()

    orig_new_case_id_pairs = [
        (orig_id, cb.case_id) for orig_id, cb in processed_cases.items()
    ]
    return orig_new_case_id_pairs, errors
