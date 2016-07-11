import collections
import copy
import datetime

from dateutil import parser
from jsonobject.exceptions import BadValueError

from casexml.apps.case.xform import extract_case_blocks, get_case_ids_from_form
from corehq.apps.change_feed import topics
from corehq.apps.change_feed.consumer.feed import KafkaChangeFeed
from corehq.apps.receiverwrapper.util import get_app_version_info
from corehq.elastic import get_es_new
from corehq.form_processor.backends.sql.dbaccessors import FormReindexAccessor
from corehq.form_processor.utils.xform import add_couch_properties_to_sql_form_json
from corehq.pillows.mappings.xform_mapping import XFORM_INDEX_INFO
from corehq.pillows.utils import get_user_type
from corehq.util.doc_processor.couch import CouchDocumentProvider
from corehq.util.doc_processor.sql import SqlDocumentProvider
from couchforms.const import RESERVED_WORDS, DEVICE_LOG_XMLNS
from couchforms.jsonobject_extensions import GeoPointProperty
from couchforms.models import XFormInstance, XFormArchived, XFormError, XFormDeprecated, \
    XFormDuplicate, SubmissionErrorLog
from pillowtop.checkpoints.manager import PillowCheckpoint, PillowCheckpointEventHandler
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processors.elastic import ElasticProcessor
from pillowtop.reindexer.reindexer import ResumableBulkElasticPillowReindexer
from .base import HQPillow

UNKNOWN_VERSION = 'XXX'
UNKNOWN_UIVERSION = 'XXX'


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
            items.extend(flatten(v, new_key, delimiter).items())
        elif not isinstance(v, list):
            items.append((new_key, v))
    return dict(items)


class XFormPillow(HQPillow):
    document_class = XFormInstance
    couch_filter = "couchforms/xforms"
    es_alias = "xforms"
    es_type = XFORM_INDEX_INFO.type
    es_index = XFORM_INDEX_INFO.index
    include_docs = False

    # for simplicity, the handlers are managed on the domain level
    handler_domain_map = {}
    default_mapping = XFORM_INDEX_INFO.mapping

    def change_transform(self, doc_dict):
        if not xform_pillow_filter(doc_dict):
            return transform_xform_for_elasticsearch(doc_dict)


def xform_pillow_filter(doc_dict):
    """
    :return: True to filter out doc
    """
    return (
        doc_dict.get('xmlns', None) == DEVICE_LOG_XMLNS or
        doc_dict.get('domain', None) is None or
        doc_dict['form'] is None
    )


def transform_xform_for_elasticsearch(doc_dict, include_props=True):
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
            doc_ret['form']['meta']['appVersion'] = doc_ret['form']['meta']['appVersion'].get('#text')

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

    case_blocks = extract_case_blocks(doc_ret)
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

    doc_ret["__retrieved_case_ids"] = list(get_case_ids_from_form(doc_dict))
    if include_props:
        form_props = ["%s:%s" % (k, v) for k, v in flatten(doc_ret['form']).iteritems()]
        doc_ret["__props_for_querying"] = form_props
    return doc_ret


def prepare_sql_form_json_for_elasticsearch(sql_form_json):
    prepped_form = transform_xform_for_elasticsearch(sql_form_json)
    if prepped_form:
        add_couch_properties_to_sql_form_json(prepped_form)

    return prepped_form


def get_xform_to_elasticsearch_pillow(pillow_id='XFormToElasticsearchPillow'):
    checkpoint = PillowCheckpoint(
        'all-xforms-to-elasticsearch',
    )
    form_processor = ElasticProcessor(
        elasticsearch=get_es_new(),
        index_info=XFORM_INDEX_INFO,
        doc_prep_fn=transform_xform_for_elasticsearch
    )
    kafka_change_feed = KafkaChangeFeed(topics=[topics.FORM, topics.FORM_SQL], group_id='forms-to-es')
    return ConstructedPillow(
        name=pillow_id,
        checkpoint=checkpoint,
        change_feed=kafka_change_feed,
        processor=form_processor,
        change_processed_event_handler=MultiTopicCheckpointEventHandler(
            checkpoint=checkpoint, checkpoint_frequency=100, change_feed=kafka_change_feed
        ),
    )


def get_couch_form_reindexer():
    iteration_key = "CouchXFormToElasticsearchPillow_{}_reindexer".format(XFORM_INDEX_INFO.index)
    doc_provider = CouchDocumentProvider(iteration_key, doc_types=[
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
        doc_transform=transform_xform_for_elasticsearch
    )


def get_sql_form_reindexer():
    iteration_key = "SqlXFormToElasticsearchPillow_{}_reindexer".format(XFORM_INDEX_INFO.index)
    doc_provider = SqlDocumentProvider(iteration_key, FormReindexAccessor())
    return ResumableBulkElasticPillowReindexer(
        doc_provider,
        elasticsearch=get_es_new(),
        index_info=XFORM_INDEX_INFO,
        doc_transform=prepare_sql_form_json_for_elasticsearch
    )
