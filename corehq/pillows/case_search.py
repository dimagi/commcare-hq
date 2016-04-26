import traceback
from collections import OrderedDict
from cStringIO import StringIO

from django.db import ProgrammingError
from django.core.mail import mail_admins

from casexml.apps.case.models import CommCareCase
from corehq.apps.case_search.exceptions import CaseSearchNotEnabledException
from corehq.apps.case_search.models import case_search_enabled_domains, \
    case_search_enabled_for_domain
from corehq.apps.change_feed import topics
from corehq.apps.change_feed.consumer.feed import KafkaChangeFeed, MultiTopicCheckpointEventHandler
from corehq.apps.es import CaseSearchES
from corehq.elastic import get_es_new
from corehq.form_processor.utils.general import should_use_sql_backend
from corehq.pillows.mappings.case_mapping import CASE_ES_TYPE
from corehq.pillows.mappings.case_search_mapping import CASE_SEARCH_INDEX, \
    CASE_SEARCH_MAPPING, CASE_SEARCH_INDEX_INFO
from pillowtop.checkpoints.manager import PillowCheckpoint
from pillowtop.es_utils import initialize_index_and_mapping
from pillowtop.feed.interface import Change
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processors.elastic import ElasticProcessor
from pillowtop.reindexer.change_providers.case import get_domain_case_change_provider
from pillowtop.reindexer.reindexer import PillowReindexer


def transform_case_for_elasticsearch(doc_dict):
    doc = {
        desired_property: doc_dict.get(desired_property)
        for desired_property in CASE_SEARCH_MAPPING['properties'].keys()
        if desired_property != 'case_properties'
    }
    doc['_id'] = doc_dict.get('_id')
    doc['case_properties'] = _get_case_properties(doc_dict)
    return doc


def _get_case_properties(doc_dict):
    domain = doc_dict.get('domain')
    assert domain
    base_case_properties = [
        {'key': 'name', 'value': doc_dict.get('name')},
        {'key': 'external_id', 'value': doc_dict.get('external_id')}
    ]
    if should_use_sql_backend(domain):
        dynamic_case_properties = OrderedDict(doc_dict['case_json'])
    else:
        dynamic_case_properties = CommCareCase.wrap(doc_dict).dynamic_case_properties()

    return base_case_properties + [
        {'key': key, 'value': value}
        for key, value in dynamic_case_properties.iteritems()
    ]


class CaseSearchPillowProcessor(ElasticProcessor):
    def process_change(self, pillow_instance, change, do_set_checkpoint):
        assert isinstance(change, Change)
        if change.metadata is not None:
            # Comes from KafkaChangeFeed (i.e. running pillowtop)
            domain = change.metadata.domain
        else:
            # comes from ChangeProvider (i.e reindexing)
            domain = change.get_document()['domain']
        if domain and case_search_enabled_for_domain(domain):
            super(CaseSearchPillowProcessor, self).process_change(
                pillow_instance, change, do_set_checkpoint
            )


def get_case_search_to_elasticsearch_pillow(pillow_id='CaseSearchToElasticsearchPillow'):
    checkpoint = PillowCheckpoint(
        'case-search-to-elasticsearch',
    )
    case_processor = CaseSearchPillowProcessor(
        elasticsearch=get_es_new(),
        index_info=CASE_SEARCH_INDEX_INFO,
        doc_prep_fn=transform_case_for_elasticsearch
    )
    change_feed = KafkaChangeFeed(topics=[topics.CASE, topics.CASE_SQL], group_id='cases-to-es')
    return ConstructedPillow(
        name=pillow_id,
        checkpoint=checkpoint,
        change_feed=change_feed,
        processor=case_processor,
        change_processed_event_handler=MultiTopicCheckpointEventHandler(
            checkpoint=checkpoint, checkpoint_frequency=100, change_feed=change_feed,
        ),
    )


def _fail_gracefully_and_tell_admins():
    f = StringIO()
    traceback.print_exc(file=f)
    mail_admins("IMPORTANT: Preindexing case_search failed because the case_search table hasn't been initialized",
                ("***Run ./manage.py migrate first then run ./manage.py ptop_preindex again***\n\n {}"
                 .format(f.getvalue())))

    class FakeReindexer(object):
        """Used so that the ptop_preindex command completes successfully
        """
        def reindex(self):
            pass

    return FakeReindexer()


def get_case_search_reindexer(domain=None):
    """Returns a reindexer that will return either all domains with case search
    enabled, or a single domain if passed in
    """
    initialize_index_and_mapping(get_es_new(), CASE_SEARCH_INDEX_INFO)
    try:
        if domain is not None:
            if not case_search_enabled_for_domain(domain):
                raise CaseSearchNotEnabledException("{} does not have case search enabled".format(domain))
            domains = [domain]
        else:
            # return changes for all enabled domains
            domains = case_search_enabled_domains()

        change_provider = get_domain_case_change_provider(domains=domains)
    except ProgrammingError:
        # The db hasn't been intialized yet, so skip this reindex and complain.
        return _fail_gracefully_and_tell_admins()
    else:
        return PillowReindexer(
            get_case_search_to_elasticsearch_pillow(),
            change_provider=change_provider
        )


def delete_case_search_cases(domain):
    if domain is None or isinstance(domain, dict):
        raise TypeError("Domain attribute is required")

    query = {'query': CaseSearchES().domain(domain).raw_query['query']}
    get_es_new().delete_by_query(
        index=CASE_SEARCH_INDEX,
        doc_type=CASE_ES_TYPE,
        body=query,
    )
