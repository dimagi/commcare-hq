from dimagi.ext import jsonobject
from pillowtop.es_utils import get_all_elasticsearch_pillow_classes


class ElasticsearchIndexInfo(jsonobject.JsonObject):
    index = jsonobject.StringProperty(required=True)
    alias = jsonobject.StringProperty()


def get_all_expected_es_indices():
    """
    Get all expected elasticsearch indices according to the currently running code
    """
    seen_indices = set()
    pillows = get_all_elasticsearch_pillow_classes()
    for pillow in pillows:
        assert pillow.es_index not in seen_indices
        yield ElasticsearchIndexInfo(index=pillow.es_index, alias=pillow.es_alias)
        seen_indices.add(pillow.es_index)
