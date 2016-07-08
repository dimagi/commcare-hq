from corehq.apps.app_manager.models import ApplicationBase, Application, RemoteApp
from corehq.apps.app_manager.util import get_correct_app_class
from corehq.apps.change_feed import topics
from corehq.apps.change_feed.consumer.feed import KafkaChangeFeed
from corehq.elastic import get_es_new
from corehq.pillows.mappings.app_mapping import APP_INDEX_INFO
from pillowtop.checkpoints.manager import PillowCheckpoint, PillowCheckpointEventHandler
from pillowtop.listener import AliasedElasticPillow
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processors import ElasticProcessor
from pillowtop.reindexer.reindexer import ResumableBulkElasticPillowReindexer


class AppPillow(AliasedElasticPillow):
    """
    Simple/Common Case properties Indexer
    """

    document_class = ApplicationBase
    couch_filter = "app_manager/all_apps"
    es_timeout = 60
    es_alias = APP_INDEX_INFO.alias
    es_type = APP_INDEX_INFO.type
    es_meta = APP_INDEX_INFO.meta
    es_index = APP_INDEX_INFO.index
    default_mapping = APP_INDEX_INFO.mapping

    def change_transform(self, doc_dict):
        return transform_app_for_es(doc_dict)


def transform_app_for_es(doc_dict):
    # perform any lazy migrations
    doc = get_correct_app_class(doc_dict).wrap(doc_dict)
    return doc.to_json()


def get_app_to_elasticsearch_pillow(pillow_id='ApplicationToElasticsearchPillow'):
    checkpoint = PillowCheckpoint(
        'applications-to-elasticsearch',
    )
    app_processor = ElasticProcessor(
        elasticsearch=get_es_new(),
        index_info=APP_INDEX_INFO,
        doc_prep_fn=transform_app_for_es
    )
    return ConstructedPillow(
        name=pillow_id,
        checkpoint=checkpoint,
        change_feed=KafkaChangeFeed(topics=[topics.APP], group_id='apps-to-es'),
        processor=app_processor,
        change_processed_event_handler=PillowCheckpointEventHandler(
            checkpoint=checkpoint, checkpoint_frequency=100,
        ),
    )


def get_app_reindexer():
    return ResumableBulkElasticPillowReindexer(
        name='ApplicationToElasticsearchPillow',
        doc_types=[Application, RemoteApp],
        elasticsearch=get_es_new(),
        index_info=APP_INDEX_INFO,
        doc_transform=transform_app_for_es,
    )
