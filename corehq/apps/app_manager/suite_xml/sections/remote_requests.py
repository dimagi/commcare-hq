from corehq.apps.app_manager import id_strings
from corehq.apps.app_manager.suite_xml.contributors import SuiteContributorByModule
from corehq.apps.app_manager.suite_xml.sections.details import DetailsHelper
from corehq.apps.app_manager.suite_xml.xml_models import (
    Command,
    Display,
    Instance,
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
from corehq.apps.app_manager.util import module_offers_search
from corehq.apps.app_manager.xpath import CaseTypeXpath, InstanceXpath
from corehq.util.view_utils import absolute_reverse


RESULTS_INSTANCE = 'results'  # The name of the instance where search results are stored
SESSION_INSTANCE = 'querysession'


class QuerySessionXPath(InstanceXpath):
    id = SESSION_INSTANCE

    @property
    def path(self):
        return 'session/data/{}'.format(self)


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
            domain = self.app.domain

            details_helper = DetailsHelper(self.app)

            remote_request = RemoteRequest(
                post=RemoteRequestPost(
                    url=absolute_reverse('claim_case', args=[domain]),
                    relevant=module.search_config.relevant,
                    data=[
                        QueryData(
                            key='case_id',
                            ref=QuerySessionXPath('case_id').instance(),
                            # e.g. instance('querysession')/session/data/case_id
                        ),
                    ]
                ),

                command=Command(
                    id=id_strings.search_command(module),
                    display=Display(
                        text=Text(locale_id=id_strings.case_search_locale(module)),
                    ),
                ),

                instances=[
                    Instance(
                        id=SESSION_INSTANCE,
                        src='jr://instance/session'
                    ),
                    Instance(
                        id='casedb',
                        src='jr://instance/casedb'
                    ),
                ],

                session=RemoteRequestSession(
                    queries=[
                        RemoteRequestQuery(
                            url=absolute_reverse('remote_search', args=[domain]),
                            storage_instance=RESULTS_INSTANCE,
                            data=([
                                QueryData(
                                    key='case_type',
                                    ref="'{}'".format(module.case_type)
                                ),
                                QueryData(
                                    key='include_closed',
                                    ref="'{}'".format(module.search_config.include_closed)
                                )
                            ] + [
                                QueryData(key="'{}'".format(c.property), ref="'{}'".format(c.defaultValue))
                                for c in module.search_config.default_properties
                            ]),
                            prompts=[
                                QueryPrompt(
                                    key=p.name,
                                    display=Display(
                                        text=Text(locale_id=id_strings.search_property_locale(module, p.name)),
                                    ),
                                ) for p in module.search_config.properties
                            ]
                        )
                    ],
                    data=[SessionDatum(
                        id='case_id',
                        nodeset=(CaseTypeXpath(module.case_type)
                                 .case(instance_name=RESULTS_INSTANCE)),
                        value='./@case_id',
                        detail_select=details_helper.get_detail_id_safe(module, 'case_short'),
                        detail_confirm=details_helper.get_detail_id_safe(module, 'case_long'),
                    )],
                ),

                stack=Stack(),
            )

            frame = PushFrame()
            frame.add_rewind(QuerySessionXPath('case_id').instance())
            remote_request.stack.add_frame(frame)

            return [remote_request]
        return []
