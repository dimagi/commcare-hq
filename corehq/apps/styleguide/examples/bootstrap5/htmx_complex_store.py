from corehq.apps.prototype.models.cache_store import CacheStore


class KeyValuePairStore(CacheStore):
    """
    CacheStore is a helpful prototyping tool when you need to store
    data on the server side for styleguide / demo HTMX views.

    Caution: Please don't use this for real features. It isn't battle-tested yet.
    """
    slug = 'styleguide-key-value-pairs'
    initial_value = [
        {
            "id": 1,
            "key": "color",
            "value": "Purple",
        },
    ]
