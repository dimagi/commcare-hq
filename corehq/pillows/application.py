from pillowtop.checkpoints.manager import (
    get_checkpoint_for_elasticsearch_pillow,
)
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processors import ElasticProcessor
from pillowtop.reindexer.reindexer import (
    ReindexerFactory,
    ResumableBulkElasticPillowReindexer,
)

from corehq.apps.app_manager.models import (
    Application,
    LinkedApplication,
    RemoteApp,
)
from corehq.apps.change_feed import topics
from corehq.apps.change_feed.consumer.feed import (
    KafkaChangeFeed,
    KafkaCheckpointEventHandler,
)
from corehq.apps.es.apps import app_adapter
from corehq.util.doc_processor.couch import CouchDocumentProvider


def get_app_to_elasticsearch_pillow(pillow_id='ApplicationToElasticsearchPillow', num_processes=1,
                                    process_num=0, **kwargs):
    """App pillow

    Processors:
      - :py:class:`pillowtop.processors.elastic.BulkElasticProcessor`
    """
    assert pillow_id == 'ApplicationToElasticsearchPillow', 'Pillow ID is not allowed to change'
    checkpoint = get_checkpoint_for_elasticsearch_pillow(pillow_id, app_adapter.index_name, [topics.APP])
    app_processor = ElasticProcessor(app_adapter)
    change_feed = KafkaChangeFeed(
        topics=[topics.APP], client_id='apps-to-es', num_processes=num_processes, process_num=process_num
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


class AppReindexerFactory(ReindexerFactory):
    slug = 'app'
    arg_contributors = [
        ReindexerFactory.resumable_reindexer_args,
        ReindexerFactory.elastic_reindexer_args,
    ]

    def build(self):
        iteration_key = "ApplicationToElasticsearchPillow_{}_reindexer".format(app_adapter.index_name)
        doc_provider = CouchDocumentProvider(iteration_key, [Application, RemoteApp, LinkedApplication])
        options = {
            'chunk_size': 5
        }
        options.update(self.options)
        return ResumableBulkElasticPillowReindexer(
            doc_provider,
            adapter=app_adapter,
            pillow=get_app_to_elasticsearch_pillow(),
            **options
        )
