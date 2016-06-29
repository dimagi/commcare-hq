import collections
import copy
import datetime

from jsonobject.exceptions import BadValueError

from casexml.apps.case.xform import extract_case_blocks, get_case_ids_from_form
from corehq.apps.change_feed import topics
from corehq.apps.change_feed.consumer.feed import KafkaChangeFeed, MultiTopicCheckpointEventHandler
from corehq.apps.receiverwrapper.util import get_app_version_info
from corehq.elastic import get_es_new
from corehq.form_processor.change_providers import SqlFormChangeProvider
from corehq.form_processor.utils.xform import add_couch_properties_to_sql_form_json
from corehq.pillows.mappings.xform_mapping import XFORM_MAPPING, XFORM_INDEX
from corehq.pillows.utils import get_user_type
from couchforms.jsonobject_extensions import GeoPointProperty
from .base import HQPillow
from couchforms.const import RESERVED_WORDS
from couchforms.models import XFormInstance
from dateutil import parser
from pillowtop.checkpoints.manager import PillowCheckpoint, PillowCheckpointEventHandler
from pillowtop.es_utils import ElasticsearchIndexInfo, get_index_info_from_pillow
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processors.elastic import ElasticProcessor
from pillowtop.processors.form import AppFormSubmissionTrackerProcessor
from pillowtop.reindexer.change_providers.couch import CouchViewChangeProvider
from pillowtop.reindexer.reindexer import get_default_reindexer_for_elastic_pillow, \
    ElasticPillowReindexer


UNKNOWN_VERSION = 'XXX'
UNKNOWN_UIVERSION = 'XXX'
XFORM_ES_TYPE = 'xform'


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
    es_type = XFORM_ES_TYPE
    es_index = XFORM_INDEX
    include_docs = False

    # for simplicity, the handlers are managed on the domain level
    handler_domain_map = {}
    default_mapping = XFORM_MAPPING

    def change_transform(self, doc_dict, include_props=True):
        return transform_xform_for_elasticsearch(doc_dict, include_props)


def transform_xform_for_elasticsearch(doc_dict, include_props=True):
    """
    Given an XFormInstance, return a copy that is ready to be sent to elasticsearch,
    or None, if the form should not be saved to elasticsearch
    """
    if doc_dict.get('domain', None) is None or doc_dict['form'] is None:
        # if there is no domain don't bother processing it
        return None
    else:
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


def get_sql_xform_to_elasticsearch_pillow(pillow_id='SqlXFormToElasticsearchPillow'):
    checkpoint = PillowCheckpoint(
        'sql-xforms-to-elasticsearch',
    )
    form_processor = ElasticProcessor(
        elasticsearch=get_es_new(),
        index_info=ElasticsearchIndexInfo(index=XFORM_INDEX, type=XFORM_ES_TYPE),
        doc_prep_fn=prepare_sql_form_json_for_elasticsearch
    )
    return ConstructedPillow(
        name=pillow_id,
        checkpoint=checkpoint,
        change_feed=KafkaChangeFeed(topics=[topics.FORM_SQL], group_id='sql-forms-to-es'),
        processor=form_processor,
        change_processed_event_handler=PillowCheckpointEventHandler(
            checkpoint=checkpoint, checkpoint_frequency=100,
        ),
    )


def get_couch_form_reindexer():
    return get_default_reindexer_for_elastic_pillow(
        pillow=XFormPillow(online=False),
        change_provider=CouchViewChangeProvider(
            couch_db=XFormInstance.get_db(),
            view_name='all_docs/by_doc_type',
            view_kwargs={
                'startkey': ['XFormInstance'],
                'endkey': ['XFormInstance', {}],
                'include_docs': True,
            }
        )
    )


def get_app_form_submission_tracker_pillow(pillow_id='AppFormSubmissionTrackerPillow'):
    """
    This gets a pillow which iterates through all forms and marks the corresponding app
    as having submissions. This could be expanded to be more generic and include
    other processing that needs to happen on each form
    """
    checkpoint = PillowCheckpoint('app-form-submission-tracker')
    form_processor = AppFormSubmissionTrackerProcessor()
    change_feed = KafkaChangeFeed(topics=[topics.FORM, topics.FORM_SQL], group_id='form-processsor')
    return ConstructedPillow(
        name=pillow_id,
        checkpoint=checkpoint,
        change_feed=change_feed,
        processor=form_processor,
        change_processed_event_handler=MultiTopicCheckpointEventHandler(
            checkpoint=checkpoint, checkpoint_frequency=100, change_feed=change_feed,
        ),
    )


def get_sql_form_reindexer():
    return ElasticPillowReindexer(
        pillow=get_sql_xform_to_elasticsearch_pillow(),
        change_provider=SqlFormChangeProvider(),
        elasticsearch=get_es_new(),
        index_info=_get_xform_index_info(),
    )


def _get_xform_index_info():
    return get_index_info_from_pillow(XFormPillow(online=False))
