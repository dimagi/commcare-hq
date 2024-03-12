import json
import time
from datetime import datetime, timedelta, timezone

from django.conf import settings
from django.core.management.base import CommandError
from django.db.backends.base.creation import TEST_DATABASE_PREFIX

from corehq.apps.es.exceptions import TaskError, TaskMissing
from corehq.util.es.elasticsearch import SerializationError
from corehq.util.json import CommCareJSONEncoder

TASK_POLL_DELAY = 10  # number of seconds to sleep between polling for task info


class ElasticJSONSerializer(object):
    """Modified version of ``elasticsearch.serializer.JSONSerializer``
    that uses the CommCareJSONEncoder for serializing to JSON.
    """
    mimetype = 'application/json'

    def loads(self, s):
        try:
            return json.loads(s)
        except (ValueError, TypeError) as e:
            raise SerializationError(s, e)

    def dumps(self, data):
        # don't serialize strings
        if isinstance(data, str):
            return data
        try:
            return json.dumps(data, cls=CommCareJSONEncoder)
        except (ValueError, TypeError) as e:
            raise SerializationError(data, e)


def values_list(hits, *fields, **kwargs):
    """modeled after django's QuerySet.values_list"""
    flat = kwargs.pop('flat', False)
    if kwargs:
        raise TypeError('Unexpected keyword arguments to values_list: %s'
                        % (list(kwargs),))
    if flat and len(fields) > 1:
        raise TypeError("'flat' is not valid when values_list is called with more than one field.")
    if not fields:
        raise TypeError('must be called with at least one field')
    if flat:
        field, = fields
        return [hit.get(field) for hit in hits]
    else:
        return [tuple(hit.get(field) for field in fields) for hit in hits]


def flatten_field_dict(results, fields_property='fields'):
    """
    In ElasticSearch 1.3, the return format was changed such that field
    values are always returned as lists, where as previously they would
    be returned as scalars if the field had a single value, and returned
    as lists if the field had multiple values.
    This method restores the behavior of 0.90 .

    https://www.elastic.co/guide/en/elasticsearch/reference/1.3/_return_values.html
    """
    field_dict = results.get(fields_property, {})
    for key, val in field_dict.items():
        new_val = val
        if type(val) is list and len(val) == 1:
            new_val = val[0]
        field_dict[key] = new_val
    return field_dict


def es_format_datetime(val):
    """
    Takes a date or datetime object and converts it to a format ES can read
    (see DATE_FORMATS_ARR). Strings are returned unmodified.
    """
    if isinstance(val, str):
        return val
    elif isinstance(val, datetime) and val.microsecond and val.tzinfo:
        # We don't support microsec precision with timezones
        return val.astimezone(timezone.utc).replace(tzinfo=None).isoformat()
    else:
        return val.isoformat()


def check_task_progress(task_id, just_once=False):
    """
    A util to be used in management commands to check the state of a task in ES.
    If just_once is set to False it will continuoslly poll for task stats until task is completed.
    Returns true if the task is completed
    """
    from corehq.apps.es.client import manager

    node_id = task_id.split(':')[0]
    node_name = manager.get_node_info(node_id, metric="name")
    print(f"Looking for task with ID '{task_id}' running on '{node_name}'")
    progress_data = []
    while True:
        try:
            task_details = manager.get_task(task_id=task_id)
        except TaskMissing:
            raise CommandError(f"Task with id {task_id} not found")
        except TaskError as err:
            raise CommandError(f"Fetching task failed: {err}")
        status = task_details["status"]
        total = status["total"]
        if total:  # total can be 0 initially
            created, updated = status["created"], status["updated"]
            deleted, conflicts = status["deleted"], status["version_conflicts"]
            progress = created + updated + deleted + conflicts
            progress_percent = progress / total * 100

            running_time_nanos = task_details["running_time_in_nanos"]
            run_time = timedelta(microseconds=running_time_nanos / 1000)

            remaining_time_absolute = 'unknown'
            remaining_time_relative = ''
            if progress:
                progress_data.append({
                    "progress": progress,
                    "time": time.monotonic() * 1000000000
                })

                remaining = total - progress
                # estimate based on progress since beginning of task
                remaining_nanos_absolute = running_time_nanos / progress * remaining
                remaining_time_absolute = timedelta(microseconds=remaining_nanos_absolute / 1000)
                if len(progress_data) > 1:
                    # estimate based on last 12 loops of data
                    progress_nanos = progress_data[-1]["time"] - progress_data[0]["time"]
                    progress_diff = progress_data[-1]["progress"] - progress_data[0]["progress"]
                    progress_data = progress_data[-12:]  # truncate progress data
                    if progress_diff:
                        remaining_nanos = progress_nanos / progress_diff * remaining
                        remaining_time_relative = timedelta(microseconds=remaining_nanos / 1000)
                    else:
                        # avoid ZeroDivisionError
                        remaining_time_relative = ''

            print(f"Progress {progress_percent:.2f}% ({progress} / {total}). "
                  f"Elapsed time: {_format_timedelta(run_time)}. "
                  f"Estimated remaining time: "
                  f"(average since start = {_format_timedelta(remaining_time_absolute)}) "
                  f"(recent average = {_format_timedelta(remaining_time_relative)})  "
                  f"Task ID: {task_id}")
        if task_details.get("completed"):
            return True
        if just_once:
            return
        time.sleep(TASK_POLL_DELAY)


def _format_timedelta(td):
    out = str(td)
    return out.split(".")[0]


def sorted_mapping(mapping):
    """Return a recursively sorted Elastic mapping."""
    if isinstance(mapping, dict):
        mapping_ = {}
        for key, value in sorted(mapping.items(), key=mapping_sort_key):
            mapping_[key] = sorted_mapping(value)
        return mapping_
    if isinstance(mapping, (tuple, list)):
        return [sorted_mapping(item) for item in mapping]
    return mapping


def mapping_sort_key(item):
    key, value = item
    return 1 if key == "properties" else 0, key, value


def index_runtime_name(name):
    # transform the name if testing
    return f"{TEST_DATABASE_PREFIX}{name}" if settings.UNIT_TESTING else name


def get_es_reindex_setting_value(name, default):
    """
    :name: name of the multiplex or swap setting like ES_APPS_INDEX_MULTIPLEXED/ES_APPS_INDEX_SWAPPED
    :default: default value if the setting is not set in localsettings.py. Should be True or False
    Returns the default value of multiplexed/swapped settings if
    `ES_MULTIPLEX_TO_VERSION` is not set or is not set to desired version.
    """
    from corehq.apps.es.const import ES_REINDEX_LOG

    if ES_REINDEX_LOG[-1] != getattr(settings, 'ES_MULTIPLEX_TO_VERSION', None):
        return default
    return getattr(settings, name, default)
