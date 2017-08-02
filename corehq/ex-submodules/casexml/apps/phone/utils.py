import logging

from django.conf import settings

from corehq.toggles import BLOBDB_RESTORE
from corehq.util.datadog.gauges import datadog_counter


def get_restore_response_class(domain):
    from casexml.apps.phone.restore import BlobRestoreResponse, FileRestoreResponse

    if BLOBDB_RESTORE.enabled(domain):
        return BlobRestoreResponse
    return FileRestoreResponse


def delete_sync_logs(before_date, limit=1000):
    from casexml.apps.phone.dbaccessors.sync_logs_by_user import get_synclog_ids_before_date
    from casexml.apps.phone.models import SyncLog
    from dimagi.utils.couch.database import iter_bulk_delete_with_doc_type_verification
    sync_log_ids = get_synclog_ids_before_date(before_date, limit)
    return iter_bulk_delete_with_doc_type_verification(SyncLog.get_db(), sync_log_ids, 'SyncLog', chunksize=5)


def record_restore_timing(restore_config, status):
    domain = restore_config.domain
    timing = restore_config.timing_context
    sync_log = restore_config.restore_state.current_sync_log
    duration = timing.duration if timing is not None else -1
    if duration > 20 or status == 412:
        sync_log_id = sync_log._id if sync_log else None
        log = logging.getLogger(__name__)
        log.info("restore %s: domain=%s status=%s duration=%.3f",
                 sync_log_id, domain, status, duration)
    tags = [
        u'status_code:{}'.format(status),
    ]
    env = settings.SERVER_ENVIRONMENT
    if (env, domain) in settings.RESTORE_TIMING_DOMAINS:
        tags.append(u'domain:{}'.format(domain))
    if timing is not None:
        for timer in timing.to_list(exclude_root=True):
            if timer.name in RESTORE_SEGMENTS:
                segment = RESTORE_SEGMENTS[timer.name]
                bucket = _get_time_bucket(timer.duration)
                datadog_counter(
                    'commcare.restores.{}'.format(segment),
                    tags=tags + ['duration:%s' % bucket],
                )
        tags.append('duration:%s' % _get_time_bucket(timing.duration))
    datadog_counter('commcare.restores.count', tags=tags)


RESTORE_SEGMENTS = {
    "FixtureElementProvider": "fixtures",
    "CasePayloadProvider": "cases",
}


def _get_time_bucket(duration):
    """Get time bucket for the given duration

    Bucket restore times because datadog's histogram is too limited

    Basically restore frequency is not high enough to have a meaningful
    time distribution with datadog's 10s aggregation window, especially
    with tags. More details:
    https://help.datadoghq.com/hc/en-us/articles/211545826
    """
    if duration < 5:
        return "lt_005s"
    if duration < 20:
        return "lt_020s"
    if duration < 60:
        return "lt_060s"
    if duration < 120:
        return "lt_120s"
    return "over_120s"
