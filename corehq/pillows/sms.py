from corehq.apps.change_feed import topics
from corehq.apps.change_feed.consumer.feed import KafkaChangeFeed
from corehq.elastic import get_es_new
from corehq.apps.sms.models import SMSLog
from corehq.pillows.mappings.sms_mapping import SMS_MAPPING, SMS_INDEX, SMS_META, SMS_TYPE
from dimagi.utils.decorators.memoized import memoized
from pillowtop.checkpoints.manager import PillowCheckpoint, PillowCheckpointEventHandler
from pillowtop.es_utils import ElasticsearchIndexInfo
from pillowtop.listener import AliasedElasticPillow
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processors.elastic import ElasticProcessor


SMS_PILLOW_CHECKPOINT_ID = 'sql-sms-to-es'
SMS_PILLOW_KAFKA_CONSUMER_GROUP_ID = 'sql-sms-to-es'

ES_SMS_INDEX = SMS_INDEX


class SMSPillow(AliasedElasticPillow):
    """
    Simple/Common Case properties Indexer
    """

    document_class = SMSLog   # while this index includes all users,
                                    # I assume we don't care about querying on properties specfic to WebUsers
    couch_filter = "sms/all_logs"
    es_timeout = 60
    es_alias = "smslogs"
    es_type = SMS_TYPE
    es_meta = SMS_META
    es_index = ES_SMS_INDEX
    default_mapping = SMS_MAPPING

    @classmethod
    @memoized
    def calc_meta(cls):
        #todo: actually do this correctly

        """
        override of the meta calculator since we're separating out all the types,
        so we just do a hash of the "prototype" instead to determined md5
        """
        return cls.calc_mapping_hash({"es_meta": cls.es_meta, "mapping": cls.default_mapping})

    def change_transport(self, doc_dict):
        # SMS changes don't go to couch anymore. Let the SqlSMSPillow process
        # changes from now on.
        # Also, we explicitly need this to be a no-op because we're going to
        # delete all sms from couch and don't want them to be deleted from
        # elasticsearch.
        return


def get_sql_sms_pillow(pillow_id):
    checkpoint = PillowCheckpoint(SMS_PILLOW_CHECKPOINT_ID)
    processor = ElasticProcessor(
        elasticsearch=get_es_new(),
        index_info=ElasticsearchIndexInfo(index=ES_SMS_INDEX, type=ES_SMS_TYPE),
        doc_prep_fn=lambda x: x
    )
    return ConstructedPillow(
        name=pillow_id,
        checkpoint=checkpoint,
        change_feed=KafkaChangeFeed(topics=[topics.SMS], group_id=SMS_PILLOW_KAFKA_CONSUMER_GROUP_ID),
        processor=processor,
        change_processed_event_handler=PillowCheckpointEventHandler(
            checkpoint=checkpoint, checkpoint_frequency=100,
        ),
    )
