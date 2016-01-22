import select
import json
import psycopg2.extensions
from kafka import KeyedProducer
from pillowtop.feed.interface import ChangeMeta

from ..data_sources import get_document_store, POSTGRES
from ..utils import send_to_kafka

CHANNELS = {
    XFormChannel.name: XFormChannel
}


class PostgresProducer(object):
    """
    Producer that pushes changes to Kafka
    """

    def __init__(self, kafka, data_source_type, data_source_name):
        self._kafka = kafka
        self._producer = KeyedProducer(self._kafka)
        self._conn = get_document_store(POSTGRES)
        self._conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
        self._data_source_type = data_source_type
        self._channel = CHANNELS[data_source_name]()

    def listen(self):
        # Each instance of PostgresProducer will take up one connection to the master database. Keep these to
        # a minimum
        curs = self._conn.cursor()
        curs.execute("LISTEN {};".format(self._channel.name))

        while True:
            #  http://initd.org/psycopg/docs/advanced.html#asynchronous-notifications
            result = select.select([self._conn], [], [], 5)
            if result == ([], [], []):
                print "Timeout"
            else:
                self._conn.poll()
                while self._conn.notifies:
                    notify = self._conn.notifies.pop(0)
                    payload = json.loads(notify.payload)  # Have channel wrap this?

                    change_meta = ChangeMeta(
                        document_id=payload.id,
                        data_source_type=self._data_source_type,
                        data_source_name=self._data_source_name,
                        document_type=None,
                        document_subtype=None,
                        domain=payload.get('domain', None),
                        is_deletion=payload.deleted,
                    )

                    send_to_kafka(
                        self._producer,
                        self._channel.name,
                        change_meta,
                    )

                    print "Got NOTIFY:", notify.pid, notify.channel, notify.payload
