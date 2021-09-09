import collections
import copy
import datetime

from dateutil import parser
from django.conf import settings
from jsonobject.exceptions import BadValueError

from casexml.apps.case.exceptions import PhoneDateValueError
from casexml.apps.case.xform import extract_case_blocks
from casexml.apps.case.xml.parser import CaseGenerationException, case_update_from_block
from corehq.apps.change_feed.topics import FORM_TOPICS
from corehq.apps.change_feed.consumer.feed import KafkaChangeFeed, KafkaCheckpointEventHandler
from corehq.apps.data_interfaces.pillow import CaseDeduplicationProcessor
from corehq.apps.receiverwrapper.util import get_app_version_info
from corehq.apps.userreports.data_source_providers import DynamicDataSourceProvider, StaticDataSourceProvider
from corehq.apps.userreports.pillow import ConfigurableReportPillowProcessor, ConfigurableReportTableManager
from corehq.elastic import get_es_new
from corehq.form_processor.backends.sql.dbaccessors import FormReindexAccessor
from corehq.pillows.base import is_couch_change_for_sql_domain
from corehq.pillows.mappings.reportxform_mapping import REPORT_XFORM_INDEX_INFO
from corehq.pillows.mappings.xform_mapping import XFORM_INDEX_INFO
from corehq.pillows.user import UnknownUsersProcessor
from corehq.pillows.utils import get_user_type, format_form_meta_for_es
from corehq.util.doc_processor.couch import CouchDocumentProvider
from corehq.util.doc_processor.sql import SqlDocumentProvider
from couchforms.const import RESERVED_WORDS, DEVICE_LOG_XMLNS
from couchforms.jsonobject_extensions import GeoPointProperty
from couchforms.models import XFormInstance, XFormArchived, XFormError, XFormDeprecated, \
    XFormDuplicate, SubmissionErrorLog
from pillowtop.checkpoints.manager import KafkaPillowCheckpoint, get_checkpoint_for_elasticsearch_pillow
from pillowtop.const import DEFAULT_PROCESSOR_CHUNK_SIZE
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processors.form import FormSubmissionMetadataTrackerProcessor
from pillowtop.processors.elastic import BulkElasticProcessor, ElasticProcessor
from pillowtop.reindexer.reindexer import ResumableBulkElasticPillowReindexer, ReindexerFactory


def is_valid_date(txt):
    try:
        if txt and parser.parse(txt):
            return True
    except Exception:
        pass
    return False


# modified from: http://stackoverflow.com/questions/6027558/flatten-nested-python-dictionaries-compressing-keys
def flatten(d, parent_key='', delimiter='/'):
    items = []
    for k, v in d.items():
        if k in RESERVED_WORDS:
            continue
        new_key = parent_key + delimiter + k if parent_key else k
        if isinstance(v, collections.MutableMapping):
            items.extend(list(flatten(v, new_key, delimiter).items()))
        elif not isinstance(v, list):
            items.append((new_key, v))
    return dict(items)


def xform_pillow_filter(doc_dict):
    """
    :return: True to filter out doc
    """
    return (
        doc_dict.get('xmlns', None) == DEVICE_LOG_XMLNS or
        doc_dict.get('domain', None) is None or
        doc_dict['form'] is None
    )


def transform_xform_for_elasticsearch(doc_dict):
    """
    Given an XFormInstance, return a copy that is ready to be sent to elasticsearch,
    or None, if the form should not be saved to elasticsearch
    """
    doc_ret = copy.deepcopy(doc_dict)

    if 'meta' in doc_ret['form']:
        if not is_valid_date(doc_ret['form']['meta'].get('timeEnd', None)):
            doc_ret['form']['meta']['timeEnd'] = None
        if not is_valid_date(doc_ret['form']['meta'].get('timeStart', None)):
            doc_ret['form']['meta']['timeStart'] = None

        # Some docs have their @xmlns and #text here
        if isinstance(doc_ret['form']['meta'].get('appVersion'), dict):
            doc_ret['form']['meta'] = format_form_meta_for_es(doc_ret['form']['meta'])

        app_version_info = get_app_version_info(
            doc_ret['domain'],
            doc_ret.get('build_id'),
            doc_ret.get('version'),
            doc_ret['form']['meta'],
        )
        doc_ret['form']['meta']['commcare_version'] = app_version_info.commcare_version
        doc_ret['form']['meta']['app_build_version'] = app_version_info.build_version

        try:
            geo_point = GeoPointProperty().wrap(doc_ret['form']['meta']['location'])
            doc_ret['form']['meta']['geo_point'] = geo_point.lat_lon
        except (KeyError, BadValueError):
            doc_ret['form']['meta']['geo_point'] = None
            pass

    try:
        user_id = doc_ret['form']['meta']['userID']
    except KeyError:
        user_id = None
    doc_ret['user_type'] = get_user_type(user_id)
    doc_ret['inserted_at'] = datetime.datetime.utcnow().isoformat()

    try:
        case_blocks = extract_case_blocks(doc_ret)
    except PhoneDateValueError:
        pass
    else:
        for case_dict in case_blocks:
            for date_modified_key in ['date_modified', '@date_modified']:
                if not is_valid_date(case_dict.get(date_modified_key, None)):
                    if case_dict.get(date_modified_key) == '':
                        case_dict[date_modified_key] = None
                    else:
                        case_dict.pop(date_modified_key, None)

            # convert all mapped dict properties to nulls if they are empty strings
            for object_key in ['index', 'attachment', 'create', 'update']:
                if object_key in case_dict and not isinstance(case_dict[object_key], dict):
                    case_dict[object_key] = None

        try:
            doc_ret["__retrieved_case_ids"] = list(set(case_update_from_block(cb).id for cb in case_blocks))
        except CaseGenerationException:
            doc_ret["__retrieved_case_ids"] = []

    if 'backend_id' not in doc_ret:
        doc_ret['backend_id'] = 'couch'

    return doc_ret


def get_xform_to_elasticsearch_pillow(pillow_id='XFormToElasticsearchPillow', num_processes=1,
                                      process_num=0, **kwargs):
    """XForm change processor that sends form data to Elasticsearch

    Processors:
      - :py:class:`pillowtop.processors.elastic.ElasticProcessor`
    """
    # todo; To remove after full rollout of https://github.com/dimagi/commcare-hq/pull/21329/
    assert pillow_id == 'XFormToElasticsearchPillow', 'Pillow ID is not allowed to change'
    checkpoint = get_checkpoint_for_elasticsearch_pillow(pillow_id, XFORM_INDEX_INFO, FORM_TOPICS)
    form_processor = ElasticProcessor(
        elasticsearch=get_es_new(),
        index_info=XFORM_INDEX_INFO,
        doc_prep_fn=transform_xform_for_elasticsearch,
        doc_filter_fn=xform_pillow_filter,
        change_filter_fn=is_couch_change_for_sql_domain
    )
    kafka_change_feed = KafkaChangeFeed(
        topics=FORM_TOPICS, client_id='forms-to-es', num_processes=num_processes, process_num=process_num
    )
    return ConstructedPillow(
        name=pillow_id,
        checkpoint=checkpoint,
        change_feed=kafka_change_feed,
        processor=form_processor,
        change_processed_event_handler=KafkaCheckpointEventHandler(
            checkpoint=checkpoint, checkpoint_frequency=100, change_feed=kafka_change_feed
        ),
    )


def get_xform_pillow(pillow_id='xform-pillow', ucr_division=None,
                     include_ucrs=None, exclude_ucrs=None,
                     num_processes=1, process_num=0, ucr_configs=None, skip_ucr=False,
                     processor_chunk_size=DEFAULT_PROCESSOR_CHUNK_SIZE,
                     topics=None, dedicated_migration_process=False, **kwargs):
    """Generic XForm change processor

    Processors:
      - :py:class:`corehq.apps.userreports.pillow.ConfigurableReportPillowProcessor` (disabled when skip_ucr=True)
      - :py:class:`pillowtop.processors.elastic.BulkElasticProcessor`
      - :py:class:`corehq.pillows.user.UnknownUsersProcessor` (disabled when RUN_UNKNOWN_USER_PILLOW=False)
      - :py:class:`pillowtop.form.FormSubmissionMetadataTrackerProcessor` (disabled when RUN_FORM_META_PILLOW=False)
      - :py:class:`corehq.apps.data_interfaces.pillow.CaseDeduplicationPillow``
    """
    # avoid circular dependency
    from corehq.pillows.reportxform import transform_xform_for_report_forms_index, report_xform_filter
    from corehq.pillows.mappings.user_mapping import USER_INDEX
    if topics:
        assert set(topics).issubset(FORM_TOPICS), "This is a pillow to process cases only"
    topics = topics or FORM_TOPICS
    change_feed = KafkaChangeFeed(
        topics, client_id=pillow_id, num_processes=num_processes, process_num=process_num,
        dedicated_migration_process=dedicated_migration_process
    )

    table_manager = ConfigurableReportTableManager(
        data_source_providers=[
            DynamicDataSourceProvider('XFormInstance'),
            StaticDataSourceProvider('XFormInstance')
        ],
        ucr_division=ucr_division,
        include_ucrs=include_ucrs,
        exclude_ucrs=exclude_ucrs,
        run_migrations=(process_num == 0),  # only first process runs migrations
    )
    ucr_processor = ConfigurableReportPillowProcessor(table_manager)
    if ucr_configs:
        table_manager.bootstrap(ucr_configs)
    xform_to_es_processor = BulkElasticProcessor(
        elasticsearch=get_es_new(),
        index_info=XFORM_INDEX_INFO,
        doc_prep_fn=transform_xform_for_elasticsearch,
        doc_filter_fn=xform_pillow_filter,
        change_filter_fn=is_couch_change_for_sql_domain
    )
    unknown_user_form_processor = UnknownUsersProcessor()
    form_meta_processor = FormSubmissionMetadataTrackerProcessor()
    checkpoint_id = "{}-{}-{}-{}".format(
        pillow_id, XFORM_INDEX_INFO.index, REPORT_XFORM_INDEX_INFO.index, USER_INDEX)
    checkpoint = KafkaPillowCheckpoint(checkpoint_id, topics)
    event_handler = KafkaCheckpointEventHandler(
        checkpoint=checkpoint, checkpoint_frequency=1000, change_feed=change_feed,
        checkpoint_callback=ucr_processor
    )
    processors = [xform_to_es_processor]
    if settings.RUN_UNKNOWN_USER_PILLOW:
        processors.append(unknown_user_form_processor)
    if settings.RUN_FORM_META_PILLOW:
        processors.append(form_meta_processor)
    if settings.RUN_DEDUPLICATION_PILLOW:
        processors.append(CaseDeduplicationProcessor())

    if not settings.ENTERPRISE_MODE:
        xform_to_report_es_processor = BulkElasticProcessor(
            elasticsearch=get_es_new(),
            index_info=REPORT_XFORM_INDEX_INFO,
            doc_prep_fn=transform_xform_for_report_forms_index,
            doc_filter_fn=report_xform_filter,
            change_filter_fn=is_couch_change_for_sql_domain
        )
        processors.append(xform_to_report_es_processor)
    if not skip_ucr:
        processors.append(ucr_processor)

    return ConstructedPillow(
        name=pillow_id,
        change_feed=change_feed,
        checkpoint=checkpoint,
        change_processed_event_handler=event_handler,
        processor=processors,
        processor_chunk_size=processor_chunk_size,
        process_num=process_num,
        is_dedicated_migration_process=dedicated_migration_process and (process_num == 0)
    )


class CouchFormReindexerFactory(ReindexerFactory):
    slug = 'form'
    arg_contributors = [
        ReindexerFactory.resumable_reindexer_args,
        ReindexerFactory.elastic_reindexer_args,
    ]

    def build(self):
        iteration_key = "CouchXFormToElasticsearchPillow_{}_reindexer".format(XFORM_INDEX_INFO.index)
        doc_provider = CouchDocumentProvider(iteration_key, doc_type_tuples=[
            XFormInstance,
            XFormArchived,
            XFormError,
            XFormDeprecated,
            XFormDuplicate,
            ('XFormInstance-Deleted', XFormInstance),
            ('HQSubmission', XFormInstance),
            SubmissionErrorLog,
        ])
        return ResumableBulkElasticPillowReindexer(
            doc_provider,
            elasticsearch=get_es_new(),
            index_info=XFORM_INDEX_INFO,
            doc_filter=xform_pillow_filter,
            pillow=get_xform_to_elasticsearch_pillow(),
            doc_transform=transform_xform_for_elasticsearch,
            **self.options
        )


class SqlFormReindexerFactory(ReindexerFactory):
    slug = 'sql-form'
    arg_contributors = [
        ReindexerFactory.resumable_reindexer_args,
        ReindexerFactory.elastic_reindexer_args,
        ReindexerFactory.limit_db_args,
        ReindexerFactory.domain_arg,
    ]

    def build(self):
        limit_to_db = self.options.pop('limit_to_db', None)
        domain = self.options.pop('domain', None)

        iteration_key = "SqlXFormToElasticsearchPillow_{}_reindexer_{}_{}".format(
            XFORM_INDEX_INFO.index, limit_to_db or 'all', domain or 'all'
        )
        limit_db_aliases = [limit_to_db] if limit_to_db else None

        reindex_accessor = FormReindexAccessor(domain=domain, limit_db_aliases=limit_db_aliases)
        doc_provider = SqlDocumentProvider(iteration_key, reindex_accessor)
        return ResumableBulkElasticPillowReindexer(
            doc_provider,
            elasticsearch=get_es_new(),
            index_info=XFORM_INDEX_INFO,
            doc_filter=xform_pillow_filter,
            doc_transform=transform_xform_for_elasticsearch,
            **self.options
        )
