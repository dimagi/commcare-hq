from corehq.apps.app_manager.suite_xml.contributors import SuiteContributorByModule
from corehq.apps.app_manager.suite_xml.xml_models import (
    QueryData,
    QueryPrompt,
    SyncRequest,
    SyncRequestQuery,
    SyncRequestPost,
    SyncRequestSession,
)
from corehq.util.view_utils import absolute_reverse


class SyncRequestContributor(SuiteContributorByModule):
    """
    Adds a sync-request node, which sets the URL and query details for
    synchronous search.

    Search is available from the module's case list.

    The node looks like this::

        <sync-request>
            <post url="">
                <data key="" ref="some session based xpath expr"/>
            </post>
            <instance/>
            <command id="...">
                <display/>
            </command>
            <session>
                <query url="some url" storage-instance="some_easy_to_reference_id">
                    <data key="some_key" ref="session-based xpath ref"/>
                    <prompt key="some_key">
                       <display/>
                    </prompt>
                </query>
                <datum/>
            </session>
            <stack/>
        </sync-request>

    """
    def get_module_contributions(self, module):
        from corehq.apps.app_manager.models import AdvancedModule, Module

        if isinstance(module, (Module, AdvancedModule)) and module.search_config:
            domain = module.get_app().domain

            sync_request = SyncRequest(
                # For synchronous searching:
                session=SyncRequestSession(
                    queries=[
                        SyncRequestQuery(
                            url=absolute_reverse('sync_search', args=[domain]),
                            data=[
                                QueryData(
                                    key='case_type',
                                    ref="'{}'".format(module.case_type)
                                ),
                            ],
                            prompts=[
                                QueryPrompt(
                                    key=s.property,
                                    display=s.label  # TODO: Display(text=s.label)? Localization?
                                ) for s in module.search_config
                            ]
                        )
                    ]
                ),
                # For case claiming:
                post=SyncRequestPost(
                    url=absolute_reverse('claim_case', args=[domain]),
                    data=[
                        QueryData(
                            key='case_id',
                            ref='session/datum/case[@id]',  # TODO: ref to ID of chosen search result
                        ),
                        QueryData(
                            key='case_type',
                            ref='session/datum/case/type',  # TODO: ref to case type of chosen search result
                        )
                    ]
                )
            )
            return [sync_request]
        return []
