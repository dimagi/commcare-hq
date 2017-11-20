# CouchDB Caching

## Why Cache?

Sometimes a page does too many couch queries that despite couch's advantages, can get slow when doing a lot.

However, while caching is easy, invalidation is hard. This framework seeks to make this easier.

## Caching Documents

cache_core has a wrapper method that calls your couch call and caches it based upon the doc_id.

## Caching Doc Properties

Likewise, cache_core can cache helper data for a given doc_id that's commonly requested. Say if there's supporting information you want
pegged to a version of a document, cache it alongside it based upon the doc_id and the custom property name. When the doc is invalidated, these
properties will be invalidated as well.

## Caching Views

Views are cached in a similar manner to the documents, using the view parameters as a key for the redis cache.

However, invalidation with views is difficult, especially with reduce views that don't necessarily have doc_ids with them.

To remedy this, we implemented a generational caching system for views, keyed by doc_type.

## Generational Caching of Views

For a given view, the view is dependent on a doc_type being part of its makeup. When a document is altered, its doc_type is noted.
If it matches a doc_type with known views that depend on it, the generation_id of these views will invalidate_all - invalidating all the views
associated with that doc_type.

The `GenerationCache` class is a registry for matching doc_types along with views to group them under 1 generational key.

At runtime, these are bootstrapped and created into a look up table to match doc changes and seeing if they need generation updates.


## Debugging

Use the debugdatabase via the devserver plugin to find slow areas of repeated queries.

You can toggle caching behavior by setting the `COUCH_CACHE_DOCS` and `COUCH_CACHE_VIEWS` localsettings flags True or False.

