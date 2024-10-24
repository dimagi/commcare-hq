import logging
from base64 import b64encode
from urllib.parse import urlencode

from corehq.apps.api.resources.messaging_event.serializers import serialize_event
from corehq.apps.api.resources.messaging_event.utils import get_limit_offset
from corehq.util import reverse

LAST_OBJECT_ID = "last_object_id"

logger = logging.getLogger(__name__)


def get_paged_data(query, request_params, api_version):
    limit = get_limit_offset("limit", request_params, 20, max_value=1000)
    objects = _get_objects(query, request_params, limit)
    return {
        "objects": [serialize_event(event) for event in objects],
        "meta": {
            "limit": limit,
            "next": _get_cursor(objects, request_params, api_version)
        }
    }


def _get_objects(query, request_params, limit):
    """Get the list of objects to return. For pages > 1 this will
    skip the first object in the page if it was present in the previous
    page (as encoded in the cursor)"""
    if request_params.is_cursor:
        objects = list(query[:limit + 1])
        last_id = request_params.get(LAST_OBJECT_ID)
        try:
            last_id = int(last_id)
        except ValueError:
            logger.debug("invalid last_object_id: '{last_id}")
        else:
            if objects[0].id == last_id:
                logger.debug(f"Skipping first object in API response: {last_id}")
                return objects[1:]  # remove the first object since it was in the last page

        logger.debug("Dropping last object in API response to keep page size consistent")
        return objects[:-1]

    logger.debug("no cursor, returning normal page")
    return list(query[:limit])


def _get_cursor(objects, request_params, api_version):
    """Generate the 'cursor' parameter which includes all query params from the current
    request excluding 'limit' as well as:
      - filter parameter for the next page e.g. date.gte = last date
      - ID of the last object in the current page to allow skipping it in the next page
    """
    if not objects:
        return None

    ascending_order = True
    if "order_by" in request_params:
        if request_params["order_by"].startswith("-"):
            ascending_order = False

    last_object = objects[-1]

    filter_param = "date.gte" if ascending_order else "date.lte"
    cursor_params = request_params.params.copy()
    cursor_params.update({
        filter_param: last_object.date.isoformat(),
        LAST_OBJECT_ID: str(last_object.id)
    })
    encoded_params = urlencode(cursor_params)
    next_params = {'cursor': b64encode(encoded_params.encode('utf-8'))}
    return reverse('api_messaging_event_list', args=[request_params.domain, api_version],
                   params=next_params, absolute=True)
