from __future__ import absolute_import
from corehq.apps.userreports.models import id_is_static
from dimagi.utils.couch import get_redis_client


def get_redis_key_for_config(config):
    if id_is_static(config._id):
        rev = 'static'
    else:
        rev = config._rev
    return 'ucr_queue-{}:{}'.format(config._id, rev)


class DataSourceResumeHelper(object):

    def __init__(self, config):
        self.config = config
        self._client = get_redis_client().client.get_client()
        self._key = get_redis_key_for_config(config)

    def get_completed_case_type_or_xmlns(self):
        return self._client.lrange(self._key, 0, -1)

    def add_completed_case_type_or_xmlns(self, case_type_or_xmlns):
        self._client.rpush(self._key, case_type_or_xmlns)

    def clear_resume_info(self):
        self._client.delete(self._key)

    def has_resume_info(self):
        return self._client.exists(self._key)
