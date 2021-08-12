from corehq import toggles
from corehq.apps.app_manager import id_strings
from corehq.apps.app_manager.suite_xml.contributors import (
    SuiteContributorByModule,
)
from corehq.apps.app_manager.suite_xml.post_process.instances import (
    get_all_instances_referenced_in_xpaths,
)
from corehq.apps.app_manager.suite_xml.post_process.workflow import (
    WorkflowDatumMeta,
)
from corehq.apps.app_manager.suite_xml.sections.details import (
    DetailsHelper,
    get_instances_for_module,
)
from corehq.apps.app_manager.suite_xml.sections.endpoints import (
    EndpointsHelper,
)
from corehq.apps.app_manager.suite_xml.xml_models import (
    Command,
    Display,
    Instance,
    Itemset,
    PushFrame,
    QueryData,
    QueryPrompt,
    RemoteRequest,
    RemoteRequestPost,
    RemoteRequestQuery,
    RemoteRequestSession,
    SessionDatum,
    Stack,
    Text,
    Hint,
)
from corehq.apps.app_manager.util import module_offers_search
from corehq.apps.app_manager.xpath import (
    CaseClaimXpath,
    CaseTypeXpath,
    InstanceXpath,
    interpolate_xpath,
)
from corehq.apps.case_search.models import CASE_SEARCH_BLACKLISTED_OWNER_ID_KEY
from corehq.util.timer import time_method
from corehq.util.view_utils import absolute_reverse

RESULTS_INSTANCE = 'results'  # The name of the instance where search results are stored
SESSION_INSTANCE = 'commcaresession'


class QuerySessionXPath(InstanceXpath):
    id = SESSION_INSTANCE

    @property
    def path(self):
        return 'session/data/{}'.format(self)


class RemoteRequestFactory(object):
    def __init__(self, module, detail_section_elements):
        self.app = module.get_app()
        self.domain = self.app.domain
        self.module = module
        self.detail_section_elements = detail_section_elements
        self.case_session_var = self.module.search_config.case_session_var

    def build_remote_request(self):
        return RemoteRequest(
            post=self.build_remote_request_post(),
            command=self.build_command(),
            instances=self.build_instances(),
            session=self.build_session(),
            stack=self.build_stack(),
        )

    def build_remote_request_post(self):
        kwargs = {
            "url": absolute_reverse('claim_case', args=[self.domain]),
            "data": [
                QueryData(
                    key='case_id',
                    ref=QuerySessionXPath(self.case_session_var).instance(),
                ),
            ],
        }
        relevant = self.get_post_relevant()
        if relevant:
            kwargs["relevant"] = relevant
        return RemoteRequestPost(**kwargs)

    def get_post_relevant(self):
        return self.module.search_config.get_relevant()

    def build_command(self):
        return Command(
            id=id_strings.search_command(self.module),
            display=Display(
                text=Text(locale_id=id_strings.case_search_locale(self.module)),
            ),
        )

    def build_instances(self):
        prompt_select_instances = [
            Instance(id=prop.itemset.instance_id, src=prop.itemset.instance_uri)
            for prop in self.module.search_config.properties
            if prop.itemset.instance_id
        ]

        query_xpaths = [QuerySessionXPath(self.case_session_var).instance()]
        query_xpaths.extend([datum.ref for datum in self._get_remote_request_query_datums()])
        query_xpaths.extend([self.module.search_config.get_relevant(), self.module.search_config.search_filter])
        query_xpaths.extend([prop.default_value for prop in self.module.search_config.properties])
        instances, unknown_instances = get_all_instances_referenced_in_xpaths(self.app, query_xpaths)
        # we use the module's case list/details view to select the datum so also
        # need these instances to be available
        instances |= get_instances_for_module(self.app, self.module, self.detail_section_elements)

        # sorted list to prevent intermittent test failures
        return sorted(set(list(instances) + prompt_select_instances), key=lambda i: i.id)

    def build_session(self):
        return RemoteRequestSession(
            queries=self.build_remote_request_queries(),
            data=self.build_remote_request_datums(),
        )

    def build_remote_request_queries(self):
        return [
            RemoteRequestQuery(
                url=absolute_reverse('app_aware_remote_search', args=[self.app.domain, self.app._id]),
                storage_instance=RESULTS_INSTANCE,
                template='case',
                data=self._get_remote_request_query_datums(),
                prompts=self.build_query_prompts(),
                default_search=self.module.search_config.default_search,
            )
        ]

    def build_remote_request_datums(self):
        details_helper = DetailsHelper(self.app)
        if self.module.case_details.short.custom_xml:
            short_detail_id = 'case_short'
            long_detail_id = 'case_long'
        else:
            short_detail_id = 'search_short'
            long_detail_id = 'search_long'

        nodeset = CaseTypeXpath(self.module.case_type).case(instance_name=RESULTS_INSTANCE)
        if toggles.USH_CASE_CLAIM_UPDATES.enabled(self.app.domain):
            additional_types = list(set(self.module.search_config.additional_case_types) - {self.module.case_type})
            if additional_types:
                nodeset = CaseTypeXpath(self.module.case_type).cases(
                    additional_types, instance_name=RESULTS_INSTANCE)
            if self.module.search_config.search_filter:
                nodeset = f"{nodeset}[{interpolate_xpath(self.module.search_config.search_filter)}]"

        return [SessionDatum(
            id=self.case_session_var,
            nodeset=nodeset,
            value='./@case_id',
            detail_select=details_helper.get_detail_id_safe(self.module, short_detail_id),
            detail_confirm=details_helper.get_detail_id_safe(self.module, long_detail_id),
        )]

    def _get_remote_request_query_datums(self):
        default_query_datums = [
            QueryData(
                key='case_type',
                ref="'{}'".format(self.module.case_type)
            ),
        ]
        additional_types = list(set(self.module.search_config.additional_case_types) - {self.module.case_type})
        for type in additional_types:
            default_query_datums.append(
                QueryData(
                    key='case_type',
                    ref="'{}'".format(type)
                )
            )
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

    def build_query_prompts(self):
        prompts = []
        for prop in self.module.search_config.properties:
            text = Text(locale_id=id_strings.search_property_locale(self.module, prop.name))
            if prop.hint:
                display = Display(
                    text=text,
                    hint=Hint(text=Text(locale_id=id_strings.search_property_hint_locale(self.module, prop.name)))
                )
            else:
                display = Display(text=text)

            kwargs = {
                'key': prop.name,
                'display': display
            }
            if not prop.appearance or prop.itemset.nodeset:
                kwargs['receive'] = prop.receiver_expression
            if prop.hidden:
                kwargs['hidden'] = prop.hidden
            if prop.appearance and self.app.enable_search_prompt_appearance:
                if prop.appearance == 'address':
                    kwargs['input_'] = prop.appearance
                else:
                    kwargs['appearance'] = prop.appearance
            if prop.input_:
                kwargs['input_'] = prop.input_
            if prop.default_value and self.app.enable_default_value_expression:
                kwargs['default_value'] = prop.default_value
            if prop.itemset.nodeset:
                kwargs['itemset'] = Itemset(
                    nodeset=prop.itemset.nodeset,
                    label_ref=prop.itemset.label,
                    value_ref=prop.itemset.value,
                    sort_ref=prop.itemset.sort,
                )
            prompts.append(QueryPrompt(**kwargs))
        return prompts

    def build_stack(self):
        stack = Stack()
        frame = PushFrame()
        frame.add_rewind(QuerySessionXPath(self.case_session_var).instance())
        stack.add_frame(frame)
        return stack


class SessionEndpointRemoteRequestFactory(RemoteRequestFactory):
    def __init__(self, module, detail_section_elements, endpoint_id, case_session_var):
        super().__init__(module, detail_section_elements)
        self.endpoint_id = endpoint_id
        self.case_session_var = case_session_var

    def get_post_relevant(self):
        return CaseClaimXpath(self.case_session_var).default_relevant()

    def build_command(self):
        return Command(
            id=f"claim_command.{self.endpoint_id}.{self.case_session_var}",
            display=Display(text=Text()),   # users never see this, but a Display and Text are required
        )

    def build_instances(self):
        query_xpaths = [QuerySessionXPath(self.case_session_var).instance()]
        query_xpaths.extend([datum.ref for datum in self._get_remote_request_query_datums()])
        query_xpaths.append(self.get_post_relevant())
        instances, unknown_instances = get_all_instances_referenced_in_xpaths(self.app, query_xpaths)

        # sorted list to prevent intermittent test failures
        return sorted(instances, key=lambda i: i.id)

    def build_remote_request_queries(self):
        return []

    def build_remote_request_datums(self):
        return [SessionDatum(
            id=self.case_session_var,
            function=QuerySessionXPath(self.case_session_var).instance(),
        )]

    def build_stack(self):
        return Stack()


class RemoteRequestContributor(SuiteContributorByModule):
    """
    Adds a remote-request node, which sets the URL and query details for
    synchronous searching and case claiming.

    Search is available from the module's case list.

    See "remote-request" in the `CommCare 2.0 Suite Definition`_ for details.


    .. _CommCare 2.0 Suite Definition: https://github.com/dimagi/commcare/wiki/Suite20#remote-request

    """

    @time_method()
    def get_module_contributions(self, module, detail_section_elements):
        elements = []
        if module_offers_search(module):
            elements.append(RemoteRequestFactory(
                module, detail_section_elements).build_remote_request()
            )
        if module.session_endpoint_id:
            elements.extend(self.get_endpoint_contributions(module, None, module.session_endpoint_id,
                                                            detail_section_elements))
        for form in module.get_forms():
            if form.session_endpoint_id:
                elements.extend(self.get_endpoint_contributions(module, form, form.session_endpoint_id,
                                                                detail_section_elements))
        return elements

    def get_endpoint_contributions(self, module, form, endpoint_id, detail_section_elements):
        helper = EndpointsHelper(self.suite, self.app)
        children = helper.get_frame_children(module, form)
        elements = []
        for child in children:
            if isinstance(child, WorkflowDatumMeta) and child.requires_selection:
                elements.append(SessionEndpointRemoteRequestFactory(
                    module, detail_section_elements, endpoint_id, child.id).build_remote_request(),
                )
        return elements
