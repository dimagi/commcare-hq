from corehq.apps.app_manager import id_strings
from corehq.apps.app_manager.suite_xml.contributors import SuiteContributorByModule
from corehq.apps.app_manager.suite_xml.sections.details import DetailsHelper
from corehq.apps.app_manager.suite_xml.xml_models import (
    Command,
    Display,
    PushFrame,
    QueryData,
    QueryPrompt,
    SessionDatum,
    Stack,
    StackDatum,
    SyncRequest,
    SyncRequestPost,
    SyncRequestQuery,
    SyncRequestSession,
    Text,
)
from corehq.apps.app_manager.xpath import XPath
from corehq.apps.case_search.models import CALCULATED_DATA, MARK_AS_CLAIMED
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

            details_helper = DetailsHelper(module.get_app())

            sync_request = SyncRequest(
                post=SyncRequestPost(
                    url=absolute_reverse('claim_case', args=[domain]),
                    data=[
                        QueryData(
                            key='case_id',
                            ref="instance('results')/case[@case_type='{}'][@status='open'][0]/@case_id".format(
                                module.case_type),
                        ),
                        QueryData(
                            key='case_type',
                            ref="instance('results')/case[@case_type='{}'][@status='open'][0]/@case_type".format(
                                module.case_type),
                        ),
                        QueryData(
                            key='case_name',
                            ref="instance('results')/case[@case_type='{}'][@status='open'][0]/name".format(
                                module.case_type),
                        ),
                    ]
                ),

                command=Command(
                    id=id_strings.search_command(module),
                    display=Display(
                        text=Text(locale_id=id_strings.case_search_locale(module)),
                    ),
                ),

                session=SyncRequestSession(
                    queries=[
                        SyncRequestQuery(
                            url=absolute_reverse('sync_search', args=[domain]),
                            storage_instance='results',
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
                    data=[SessionDatum(
                        id='case_id',
                        nodeset="instance('results')/case[@case_type='{}'][@status='open']".format(
                            module.case_type),
                        value='./@case_id',
                        detail_select=details_helper.get_detail_id_safe(module, 'case_short'),
                        detail_confirm=details_helper.get_detail_id_safe(module, 'case_long'),
                    )],
                ),

                stack=Stack(),
            )

            frame = PushFrame()
            # Open first form in module
            frame.add_command(XPath.string(id_strings.form_command(module, module.forms[0])))
            frame.add_datum(StackDatum(id=CALCULATED_DATA, value=XPath.string(MARK_AS_CLAIMED)))
            sync_request.stack.add_frame(frame)

            return [sync_request]
        return []
