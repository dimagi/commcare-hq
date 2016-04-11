from collections import OrderedDict

from casexml.apps.case.models import CommCareCase
from corehq.apps.case_search.exceptions import CaseSearchNotEnabledException
from corehq.apps.case_search.models import case_search_enabled_domains, \
    case_search_enabled_for_domain
from corehq.apps.change_feed import topics
from corehq.apps.change_feed.consumer.feed import KafkaChangeFeed
from corehq.apps.es import CaseSearchES
from corehq.elastic import get_es_new
from corehq.form_processor.utils.general import should_use_sql_backend
from corehq.pillows.case import CASE_ES_TYPE, CasePillow
from corehq.pillows.const import CASE_SEARCH_ALIAS
from corehq.pillows.mappings.case_search_mapping import CASE_SEARCH_INDEX, \
    CASE_SEARCH_MAPPING
from pillowtop.checkpoints.manager import PillowCheckpoint, \
    PillowCheckpointEventHandler
from pillowtop.es_utils import ElasticsearchIndexInfo
from pillowtop.feed.couch import change_from_couch_row
from pillowtop.feed.interface import Change
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processors.elastic import ElasticProcessor
from pillowtop.reindexer.change_providers.case import get_domain_case_change_provider
from pillowtop.reindexer.reindexer import PillowReindexer


class CaseSearchPillow(CasePillow):
    # TODO: Remove this once elasticsearch gets bootstrapped with new pillows
    # (Used in order to set up index)
    """
    Nested case properties indexer.
    """
    es_alias = CASE_SEARCH_ALIAS

    es_index = CASE_SEARCH_INDEX
    default_mapping = CASE_SEARCH_MAPPING

    def run(self, changes_dict):
        return


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
        domain = self._get_domain(change)
        change_object = self._get_change_object(change)
        if domain and case_search_enabled_for_domain(domain):
            super(CaseSearchPillowProcessor, self).process_change(
                pillow_instance, change_object, do_set_checkpoint
            )

    @staticmethod
    def _get_domain(change):
        # Changes coming from the KafkaChangeFeed provides a Change Object.
        # Changes coming from the CouchViewChangeProvider, used in the reindex
        # provides a dict that comes from the couch view. Figure out which one
        # it is and get the domain appropriately

        # TODO: when CouchViewChangeProvider provides a change object, this can be removed.

        if isinstance(change, dict):
            # If this is a dict, it is a row from the couch view, and has come
            # from the CouchViewChangeProvider. The view: 'cases_by_owner/view'
            # provides [domain, owner_id, doc.closed] as the keys
            return change.get('key', [])[0]
        elif isinstance(change, Change):
            # If this is a change object, we grab the domain directly from this
            # object
            return change.metadata.domain

    @staticmethod
    def _get_change_object(change):
        # Similar to _get_domain above, figure out if this is coming from
        # KafkaChangeFeed or CouchViewChangeProvider. We can't use the Change
        # object that this returns above, as it doesn't have the metadata
        # property when coming from a couch_row

        if isinstance(change, dict):
            return change_from_couch_row(change)
        elif isinstance(change, Change):
            return change


def get_case_search_to_elasticsearch_pillow(pillow_id='CaseSearchToElasticsearchPillow'):
    checkpoint = PillowCheckpoint(
        'case-search-to-elasticsearch',
    )
    case_processor = CaseSearchPillowProcessor(
        elasticsearch=get_es_new(),
        index_info=ElasticsearchIndexInfo(index=CASE_SEARCH_INDEX, type=CASE_ES_TYPE),
        doc_prep_fn=transform_case_for_elasticsearch
    )
    return ConstructedPillow(
        name=pillow_id,
        document_store=None,
        checkpoint=checkpoint,
        change_feed=KafkaChangeFeed(topics=[topics.CASE, topics.CASE_SQL], group_id='cases-to-es'),
        processor=case_processor,
        change_processed_event_handler=PillowCheckpointEventHandler(
            checkpoint=checkpoint, checkpoint_frequency=100,
        ),
    )


def get_case_search_reindexer(domain=None):
    """Returns a reindexer that will return either all domains with case search
    enabled, or a single domain if passed in
    """
    CaseSearchPillow()          # TODO: remove this:
    if domain is not None:
        if not case_search_enabled_for_domain(domain):
            raise CaseSearchNotEnabledException("{} does not have case search enabled".format(domain))
        domains = [domain]
    else:
        # return changes for all enabled domains
        domains = case_search_enabled_domains()

    return PillowReindexer(
        get_case_search_to_elasticsearch_pillow(),
        change_provider=get_domain_case_change_provider(domains=domains)
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
