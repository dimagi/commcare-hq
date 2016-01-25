import collections
import copy
from casexml.apps.case.xform import extract_case_blocks, get_case_ids_from_form
from corehq.apps.change_feed import topics
from corehq.apps.change_feed.consumer.feed import KafkaChangeFeed
from corehq.elastic import get_es_new
from corehq.form_processor.interfaces.dbaccessors import FormAccessors
from corehq.pillows.mappings.xform_mapping import XFORM_MAPPING, XFORM_INDEX
from .base import HQPillow
from couchforms.const import RESERVED_WORDS
from couchforms.models import XFormInstance
from dateutil import parser
from dimagi.utils.decorators.memoized import memoized
from pillowtop.checkpoints.manager import PillowCheckpoint, get_django_checkpoint_store, \
    PillowCheckpointEventHandler
from pillowtop.listener import send_to_elasticsearch
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processor import PillowProcessor


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

    @classmethod
    def get_unique_id(self):
        return XFORM_INDEX

    def change_transform(self, doc_dict, include_props=True):
        return transform_xform_for_elasticsearch(doc_dict, include_props)


def transform_xform_for_elasticsearch(doc_dict, include_props=True):
    """
    Given an XFormInstance, return a copy that is ready to be sent to elasticsearch,
    or None, if the form should not be saved to elasticsearch
    """
    if doc_dict.get('domain', None) is None:
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


class XFormToElasticProcessor(PillowProcessor):

    @property
    @memoized
    def elasticsearch(self):
        return get_es_new()

    def process_change(self, pillow_instance, change, do_set_checkpoint):
        # if you don't worry about the various configuration options for reindexing,
        # bootstrapping / dealing with the elasticsearch index, and bulk operations,
        # this is all the current code does too
        form_ready_to_go = transform_xform_for_elasticsearch(change.get_document())
        # todo: this is required for our queries, figure out how best to deal with it
        form_ready_to_go['doc_type'] = 'XFormInstance'
        doc_exists = self.elasticsearch.exists(XFORM_INDEX, change.id, XFORM_ES_TYPE)
        send_to_elasticsearch(
            index=XFORM_INDEX,
            doc_type=XFORM_ES_TYPE,
            doc_id=change.id,
            es_getter=get_es_new,
            name=pillow_instance.get_name(),
            data=form_ready_to_go,
            update=doc_exists,
        )


def get_sql_xform_to_elasticsearch_pillow():
    checkpoint = PillowCheckpoint(
        get_django_checkpoint_store(),
        'sql-xforms-to-elasticsearch',
    )
    return ConstructedPillow(
        name='SqlXFormToElasticsearchPillow',
        document_store=None,
        checkpoint=checkpoint,
        change_feed=KafkaChangeFeed(topic=topics.SQL_FORM, group_id='sql-forms-to-es'),
        processor=XFormToElasticProcessor(),
        change_processed_event_handler=PillowCheckpointEventHandler(
            checkpoint=checkpoint, checkpoint_frequency=100,
        ),
    )
