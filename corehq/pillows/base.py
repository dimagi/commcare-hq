from corehq.apps.change_feed.data_sources import SOURCE_COUCH


def is_couch_change_for_sql_domain(change):
    if not change.metadata or not change.metadata.domain:
        return False
    return change.metadata.data_source_type == SOURCE_COUCH
