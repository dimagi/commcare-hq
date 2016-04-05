from corehq.apps.app_manager import id_strings
from corehq.apps.app_manager.suite_xml.contributors import SuiteContributorByModule
from corehq.apps.app_manager.suite_xml.xml_models import (
    Command,
    Display,
    QueryData,
    QueryPrompt,
    SessionDatum,
    Stack,
    SyncRequest,
    SyncRequestPost,
    SyncRequestQuery,
    SyncRequestSession,
    Text,
)
from corehq.util.view_utils import absolute_reverse


class SyncRequestContributor(SuiteContributorByModule):
    """
    Adds a sync-request node, which sets the URL and query details for
    synchronous searching and case claiming.

    Search is available from the module's case list.

    See "sync-request" in the `CommCare 2.0 Suite Definition`_ for details.


    .. _CommCare 2.0 Suite Definition: https://github.com/dimagi/commcare/wiki/Suite20#sync-request

    """
    def get_module_contributions(self, module):
        from corehq.apps.app_manager.models import AdvancedModule, Module

        if isinstance(module, (Module, AdvancedModule)) and module.search_config:
            domain = module.get_app().domain

            sync_request = SyncRequest(
                # For synchronous searching:
                command=Command(
                    # TODO: How does <command> refer to module or case list?
                    id=id_strings.case_list_locale(module) + '.or_something',
                    display=Display(
                        text=Text(locale_id=id_strings.case_search_locale(module)),
                    ),
                ),
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
                                    display=Display(
                                        text=Text(locale_id=id_strings.search_property_locale(module, s.property)),
                                    ),
                                ) for s in module.search_config
                            ]
                        )
                    ],
                    # data=[SessionDatum()],  # TODO: Necessary? 0 or more, right?
                ),
                # stack=[Stack()],  # TODO: Necessary? 0 or more, right?
                # For case claiming:
                post=SyncRequestPost(
                    url=absolute_reverse('claim_case', args=[domain]),
                    data=[
                        QueryData(
                            key='case_id',
                            ref='session/datum[0]/case[@id]',  # TODO: ref to ID of *chosen* search result
                        ),
                        QueryData(
                            key='case_type',
                            ref='session/datum[0]/case/type',  # TODO: ref to case type of *chosen* search result
                        )
                    ]
                )
            )
            return [sync_request]
        return []
