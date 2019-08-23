from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.app_manager import id_strings
from corehq.apps.app_manager.suite_xml.contributors import SuiteContributorByModule
from corehq.apps.case_search.models import CASE_SEARCH_BLACKLISTED_OWNER_ID_KEY
from corehq.apps.app_manager.suite_xml.sections.details import DetailsHelper, get_instances_for_module
from corehq.apps.app_manager.suite_xml.xml_models import (
    Command,
    Display,
    PushFrame,
    QueryData,
    QueryPrompt,
    SessionDatum,
    Stack,
    RemoteRequest,
    RemoteRequestPost,
    RemoteRequestQuery,
    RemoteRequestSession,
    Text,
)
from corehq.apps.app_manager.suite_xml.post_process.instances import get_all_instances_referenced_in_xpaths
from corehq.apps.app_manager.util import module_offers_search
from corehq.apps.app_manager.xpath import CaseTypeXpath, InstanceXpath
from corehq.util.view_utils import absolute_reverse


RESULTS_INSTANCE = 'results'  # The name of the instance where search results are stored
SESSION_INSTANCE = 'commcaresession'


class QuerySessionXPath(InstanceXpath):
    id = SESSION_INSTANCE

    @property
    def path(self):
        return 'session/data/{}'.format(self)


class RemoteRequestFactory(object):
    def __init__(self, domain, app, module):
        self.domain = domain
        self.app = app
        self.module = module

    def build_remote_request(self):
        return RemoteRequest(
            post=self._build_remote_request_post(),
            command=self._build_command(),
            instances=self._build_instances(),
            session=self._build_session(),
            stack=self._build_stack(),
        )

    def _build_remote_request_post(self):
        return RemoteRequestPost(
            url=absolute_reverse('claim_case', args=[self.domain]),
            relevant=self.module.search_config.relevant,
            data=[
                QueryData(
                    key='case_id',
                    ref=QuerySessionXPath('case_id').instance(),
                ),
            ]
        )

    def _build_command(self):
        return Command(
            id=id_strings.search_command(self.module),
            display=Display(
                text=Text(locale_id=id_strings.case_search_locale(self.module)),
            ),
        )

    def _build_instances(self):
        query_xpaths = [datum.ref for datum in self._get_remote_request_query_datums()]
        claim_relevant_xpaths = [self.module.search_config.relevant]

        instances, unknown_instances = get_all_instances_referenced_in_xpaths(
            self.app,
            query_xpaths + claim_relevant_xpaths
        )
        # we use the module's case list/details view to select the datum so also
        # need these instances to be available
        instances |= get_instances_for_module(self.app, self.module)
        # sorted list to prevent intermittent test failures
        return sorted(list(instances), key=lambda i: i.id)

    def _build_session(self):
        return RemoteRequestSession(
            queries=self._build_remote_request_queries(),
            data=self._build_remote_request_datums(),
        )

    def _build_remote_request_queries(self):
        return [
            RemoteRequestQuery(
                url=absolute_reverse('remote_search', args=[self.app.domain]),
                storage_instance=RESULTS_INSTANCE,
                template='case',
                data=self._get_remote_request_query_datums(),
                prompts=self._build_query_prompts()
            )
        ]

    def _build_remote_request_datums(self):
        details_helper = DetailsHelper(self.app)
        if self.module.case_details.short.custom_xml:
            short_detail_id = 'case_short'
        else:
            short_detail_id = 'search_short'

        return [SessionDatum(
            id='case_id',
            nodeset=(CaseTypeXpath(self.module.case_type)
                     .case(instance_name=RESULTS_INSTANCE)),
            value='./@case_id',
            detail_select=details_helper.get_detail_id_safe(self.module, short_detail_id),
            detail_confirm=details_helper.get_detail_id_safe(self.module, 'case_long'),
        )]

    def _get_remote_request_query_datums(self):
        default_query_datums = [
            QueryData(
                key='case_type',
                ref="'{}'".format(self.module.case_type)
            ),
            QueryData(
                key='include_closed',
                ref="'{}'".format(self.module.search_config.include_closed)
            )
        ]
        extra_query_datums = [
            QueryData(key="{}".format(c.property), ref="{}".format(c.defaultValue))
            for c in self.module.search_config.default_properties
        ]
        if self.module.search_config.blacklisted_owner_ids_expression:
            extra_query_datums.append(
                QueryData(
                    key=CASE_SEARCH_BLACKLISTED_OWNER_ID_KEY,
                    ref="{}".format(self.module.search_config.blacklisted_owner_ids_expression)
                )
            )
        return default_query_datums + extra_query_datums

    def _build_query_prompts(self):
        return [
            QueryPrompt(
                key=p.name,
                display=Display(
                    text=Text(locale_id=id_strings.search_property_locale(self.module, p.name)),
                ),
            ) for p in self.module.search_config.properties
        ]

    def _build_stack(self):
        stack = Stack()
        frame = PushFrame()
        frame.add_rewind(QuerySessionXPath('case_id').instance())
        stack.add_frame(frame)
        return stack


class RemoteRequestContributor(SuiteContributorByModule):
    """
    Adds a remote-request node, which sets the URL and query details for
    synchronous searching and case claiming.

    Search is available from the module's case list.

    See "remote-request" in the `CommCare 2.0 Suite Definition`_ for details.


    .. _CommCare 2.0 Suite Definition: https://github.com/dimagi/commcare/wiki/Suite20#remote-request

    """
    def get_module_contributions(self, module):
        if module_offers_search(module):
            return [RemoteRequestFactory(self.app.domain, self.app, module).build_remote_request()]
        return []
