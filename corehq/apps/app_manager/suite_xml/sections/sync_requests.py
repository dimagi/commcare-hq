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
from corehq.apps.app_manager.util import module_offers_search
from corehq.apps.app_manager.xpath import XPath, CaseTypeXpath
from corehq.apps.case_search.models import CALCULATED_DATA, MARK_AS_CLAIMED
from corehq.util.view_utils import absolute_reverse


RESULTS_INSTANCE = 'results'  # The name of the instance where search results are stored


class SyncRequestContributor(SuiteContributorByModule):
    """
    Adds a sync-request node, which sets the URL and query details for
    synchronous searching and case claiming.

    Search is available from the module's case list.

    See "sync-request" in the `CommCare 2.0 Suite Definition`_ for details.


    .. _CommCare 2.0 Suite Definition: https://github.com/dimagi/commcare/wiki/Suite20#sync-request

    """
    def get_module_contributions(self, module):
        if module_offers_search(module):
            domain = self.app.domain

            details_helper = DetailsHelper(self.app)

            sync_request = SyncRequest(
                post=SyncRequestPost(
                    url=absolute_reverse('claim_case', args=[domain]),
                    data=[
                        QueryData(
                            key='case_id',
                            ref=(CaseTypeXpath(module.case_type)
                                 .case(instance_name=RESULTS_INSTANCE)
                                 .select(u'@status', u'open', quote=True)
                                 .select_raw(0)
                                 .slash(u'@case_id')),
                            # e.g. instance('results')/results/case[@case_type='foo'][@status='open'][0]/@case_id
                        ),
                        QueryData(
                            key='case_type',
                            ref=(CaseTypeXpath(module.case_type)
                                 .case(instance_name=RESULTS_INSTANCE)
                                 .select(u'@status', u'open', quote=True)
                                 .select_raw(0)
                                 .slash(u'@case_type')),
                        ),
                        QueryData(
                            key='case_name',
                            ref=(CaseTypeXpath(module.case_type)
                                 .case(instance_name=RESULTS_INSTANCE)
                                 .select(u'@status', u'open', quote=True)
                                 .select_raw(0)
                                 .slash(u'name')),
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
                            storage_instance=RESULTS_INSTANCE,
                            data=[
                                QueryData(
                                    key='case_type',
                                    ref="'{}'".format(module.case_type)
                                ),
                            ],
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
                                 .case(instance_name=RESULTS_INSTANCE)
                                 .select(u'@status', u'open', quote=True)),
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
