"""Utilities for assessing and repairing CouchDB corruption"""
import logging

log = logging.getLogger(__name__)


def find_missing_ids(get_doc_ids, min_tries=5, limit=100):
    """Find missing ids

    Given a function that is expected to always return the same set of
    unique ids, find all ids that are missing from some result sets.

    Returns a tuple `(missing_ids, tries)
    """
    min_tries -= 1
    missing = set()
    all_ids = set()
    no_news = 0
    for tries in range(limit):
        next_ids = get_doc_ids()
        if all_ids:
            miss = next_ids ^ all_ids
            if any(x not in missing for x in miss):
                no_news = 0
                missing.update(miss)
                all_ids.update(miss)
        else:
            all_ids.update(next_ids)
        if no_news > min_tries:
            return missing, tries + 1
        no_news += 1
    log.warning("still finding new missing docs after 100 queries")
    return missing, 100
