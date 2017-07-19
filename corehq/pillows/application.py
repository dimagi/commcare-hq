from corehq.apps.app_manager.models import Application, RemoteApp, LinkedApplication
from corehq.apps.app_manager.util import get_correct_app_class
from corehq.apps.change_feed import topics
from corehq.apps.change_feed.consumer.feed import KafkaChangeFeed, KafkaCheckpointEventHandler
from corehq.elastic import get_es_new
from corehq.pillows.mappings.app_mapping import APP_INDEX_INFO
from corehq.util.doc_processor.couch import CouchDocumentProvider
from pillowtop.checkpoints.manager import get_checkpoint_for_elasticsearch_pillow
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processors import ElasticProcessor
from pillowtop.reindexer.reindexer import ResumableBulkElasticPillowReindexer


def transform_app_for_es(doc_dict):
    # perform any lazy migrations
    doc = get_correct_app_class(doc_dict).wrap(doc_dict)
    return doc.to_json()


def get_app_to_elasticsearch_pillow(pillow_id='ApplicationToElasticsearchPillow', num_processes=1,
                                    process_num=0, **kwargs):
    assert pillow_id == 'ApplicationToElasticsearchPillow', 'Pillow ID is not allowed to change'
    checkpoint = get_checkpoint_for_elasticsearch_pillow(pillow_id, APP_INDEX_INFO, [topics.APP])
    app_processor = ElasticProcessor(
        elasticsearch=get_es_new(),
        index_info=APP_INDEX_INFO,
        doc_prep_fn=transform_app_for_es
    )
    change_feed = KafkaChangeFeed(
        topics=[topics.APP], group_id='apps-to-es', num_processes=num_processes, process_num=process_num
    )
    return ConstructedPillow(
        name=pillow_id,
        checkpoint=checkpoint,
        change_feed=change_feed,
        processor=app_processor,
        change_processed_event_handler=KafkaCheckpointEventHandler(
            checkpoint=checkpoint, checkpoint_frequency=100, change_feed=change_feed
        ),
    )


def get_app_reindexer():
    iteration_key = "ApplicationToElasticsearchPillow_{}_reindexer".format(APP_INDEX_INFO.index)
    doc_provider = CouchDocumentProvider(iteration_key, [Application, RemoteApp, LinkedApplication])
    return ResumableBulkElasticPillowReindexer(
        doc_provider,
        elasticsearch=get_es_new(),
        index_info=APP_INDEX_INFO,
        doc_transform=transform_app_for_es,
        pillow=get_app_to_elasticsearch_pillow(),
        chunk_size=5,
    )
