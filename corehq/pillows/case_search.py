from __future__ import absolute_import, unicode_literals

from collections import OrderedDict
from datetime import datetime

import six
from django.core.mail import mail_admins
from django.db import ProgrammingError

from casexml.apps.case.models import CommCareCase
from corehq.apps.case_search.const import (
    INDEXED_ON,
    SPECIAL_CASE_PROPERTIES_MAP,
    SYSTEM_PROPERTIES,
    VALUE,
)
from corehq.apps.case_search.exceptions import CaseSearchNotEnabledException
from corehq.apps.case_search.models import case_search_enabled_domains
from corehq.apps.change_feed import topics
from corehq.apps.change_feed.consumer.feed import (
    KafkaChangeFeed,
    KafkaCheckpointEventHandler,
)
from corehq.apps.es import CaseSearchES
from corehq.elastic import get_es_new
from corehq.form_processor.backends.sql.dbaccessors import CaseReindexAccessor
from corehq.form_processor.utils.general import should_use_sql_backend
from corehq.pillows.mappings.case_mapping import CASE_ES_TYPE
from corehq.pillows.mappings.case_search_mapping import (
    CASE_SEARCH_INDEX,
    CASE_SEARCH_INDEX_INFO,
    CASE_SEARCH_MAPPING,
)
from corehq.toggles import (
    CASE_LIST_EXPLORER,
    EXPLORE_CASE_DATA,
    ECD_MIGRATED_DOMAINS,
)
from corehq.util.doc_processor.sql import SqlDocumentProvider
from corehq.util.log import get_traceback_string
from corehq.util.quickcache import quickcache
from dimagi.utils.parsing import json_format_datetime
from pillowtop.checkpoints.manager import (
    get_checkpoint_for_elasticsearch_pillow,
)
from pillowtop.es_utils import initialize_index_and_mapping
from pillowtop.feed.interface import Change
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processors.elastic import ElasticProcessor
from pillowtop.reindexer.change_providers.case import (
    get_domain_case_change_provider,
)
from pillowtop.reindexer.reindexer import (
    PillowChangeProviderReindexer,
    ReindexerFactory,
    ResumableBulkElasticPillowReindexer,
)


@quickcache([], timeout=24 * 60 * 60, memoize_timeout=60)
def domains_needing_search_index():
    return set(list(case_search_enabled_domains())
               + CASE_LIST_EXPLORER.get_enabled_domains()
               + EXPLORE_CASE_DATA.get_enabled_domains()
               + ECD_MIGRATED_DOMAINS.get_enabled_domains())


def domain_needs_search_index(domain):
    return domain in domains_needing_search_index()


def transform_case_for_elasticsearch(doc_dict):
    doc = {
        desired_property: doc_dict.get(desired_property)
        for desired_property in CASE_SEARCH_MAPPING['properties'].keys()
        if desired_property not in SYSTEM_PROPERTIES
    }
    doc['_id'] = doc_dict.get('_id')
    doc[INDEXED_ON] = json_format_datetime(datetime.utcnow())
    doc['case_properties'] = _get_case_properties(doc_dict)
    return doc


def _get_case_properties(doc_dict):
    domain = doc_dict.get('domain')
    assert domain
    base_case_properties = [
        {'key': base_case_property.key, 'value': base_case_property.value_getter(doc_dict)}
        for base_case_property in list(SPECIAL_CASE_PROPERTIES_MAP.values())
    ]
    if should_use_sql_backend(domain):
        dynamic_case_properties = OrderedDict(doc_dict['case_json'])
    else:
        dynamic_case_properties = CommCareCase.wrap(doc_dict).dynamic_case_properties()

    dynamic_mapping = [{'key': key, VALUE: value} for key, value in six.iteritems(dynamic_case_properties)]

    return base_case_properties + dynamic_mapping


class CaseSearchPillowProcessor(ElasticProcessor):

    def process_change(self, change):
        assert isinstance(change, Change)
        if change.metadata is not None:
            # Comes from KafkaChangeFeed (i.e. running pillowtop)
            domain = change.metadata.domain
        else:
            # comes from ChangeProvider (i.e reindexing)
            domain = change.get_document()['domain']

        if domain and domain_needs_search_index(domain):
            super(CaseSearchPillowProcessor, self).process_change(change)


def get_case_search_processor():
    return CaseSearchPillowProcessor(
        elasticsearch=get_es_new(),
        index_info=CASE_SEARCH_INDEX_INFO,
        doc_prep_fn=transform_case_for_elasticsearch
    )


def _fail_gracefully_and_tell_admins():
    mail_admins("IMPORTANT: Preindexing case_search failed because the case_search table hasn't been initialized",
                ("***Run ./manage.py migrate first then run ./manage.py ptop_preindex again***\n\n {}"
                 .format(get_traceback_string())))

    class FakeReindexer(object):
        """Used so that the ptop_preindex command completes successfully
        """

        def reindex(self):
            pass

    return FakeReindexer()


def domain_args(parser):
    parser.add_argument(
        '--domain',
        dest='domain'
    )


class CaseSearchReindexerFactory(ReindexerFactory):
    slug = 'case-search'
    arg_contributors = [
        ReindexerFactory.limit_db_args,
        domain_args
    ]

    def build(self):
        """Returns a reindexer that will return either all domains with case search
        enabled, or a single domain if passed in
        """
        limit_to_db = self.options.pop('limit_to_db', None)
        domain = self.options.pop('domain', None)

        limit_db_aliases = [limit_to_db] if limit_to_db else None
        initialize_index_and_mapping(get_es_new(), CASE_SEARCH_INDEX_INFO)
        try:
            if domain is not None:
                if not domain_needs_search_index(domain):
                    raise CaseSearchNotEnabledException("{} does not have case search enabled".format(domain))
                domains = [domain]
            else:
                # return changes for all enabled domains
                domains = domains_needing_search_index()

            change_provider = get_domain_case_change_provider(domains=domains, limit_db_aliases=limit_db_aliases)
        except ProgrammingError:
            # The db hasn't been intialized yet, so skip this reindex and complain.
            return _fail_gracefully_and_tell_admins()
        else:
            return PillowChangeProviderReindexer(
                get_case_search_processor(),
                change_provider=change_provider,
            )


def get_case_search_to_elasticsearch_pillow(pillow_id='CaseSearchToElasticsearchPillow', num_processes=1,
                                            process_num=0, **kwargs):
    # todo; To remove after full rollout of https://github.com/dimagi/commcare-hq/pull/21329/
    assert pillow_id == 'CaseSearchToElasticsearchPillow', 'Pillow ID is not allowed to change'
    checkpoint = get_checkpoint_for_elasticsearch_pillow(pillow_id, CASE_SEARCH_INDEX_INFO, topics.CASE_TOPICS)
    case_processor = CaseSearchPillowProcessor(
        elasticsearch=get_es_new(),
        index_info=CASE_SEARCH_INDEX_INFO,
        doc_prep_fn=transform_case_for_elasticsearch
    )
    change_feed = KafkaChangeFeed(
        topics=topics.CASE_TOPICS, client_id='cases-to-es', num_processes=num_processes, process_num=process_num
    )
    return ConstructedPillow(
        name=pillow_id,
        checkpoint=checkpoint,
        change_feed=change_feed,
        processor=case_processor,
        change_processed_event_handler=KafkaCheckpointEventHandler(
            checkpoint=checkpoint, checkpoint_frequency=100, change_feed=change_feed,
        ),
    )


class ResumableCaseSearchReindexerFactory(ReindexerFactory):
    """Reindexer for case search that is supports resume.

    Can only be run for a single domain at a time and only for SQL domains.
    """
    slug = 'case-search-resumable'
    arg_contributors = [
        ReindexerFactory.resumable_reindexer_args,
        ReindexerFactory.elastic_reindexer_args,
        ReindexerFactory.limit_db_args,
    ]

    @classmethod
    def add_arguments(cls, parser):
        super(ResumableCaseSearchReindexerFactory, cls).add_arguments(parser)
        parser.add_argument(
            '--domain',
            dest='domain',
            required=True
        )

    def build(self):
        limit_to_db = self.options.pop('limit_to_db', None)
        domain = self.options.pop('domain')
        if not domain_needs_search_index(domain):
            raise CaseSearchNotEnabledException("{} does not have case search enabled".format(domain))

        assert should_use_sql_backend(domain), '{} can only be used with SQL domains'.format(self.slug)
        iteration_key = "CaseSearchResumableToElasticsearchPillow_{}_reindexer_{}_{}".format(
            CASE_SEARCH_INDEX_INFO.index, limit_to_db or 'all', domain or 'all'
        )
        limit_db_aliases = [limit_to_db] if limit_to_db else None
        accessor = CaseReindexAccessor(domain=domain, limit_db_aliases=limit_db_aliases)
        doc_provider = SqlDocumentProvider(iteration_key, accessor)
        return ResumableBulkElasticPillowReindexer(
            doc_provider,
            elasticsearch=get_es_new(),
            index_info=CASE_SEARCH_INDEX_INFO,
            doc_transform=transform_case_for_elasticsearch,
            **self.options
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
