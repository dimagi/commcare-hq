from __future__ import absolute_import
from __future__ import unicode_literals
from couchdbkit import ResourceNotFound
from django.conf import settings
from django.core.cache import cache

from corehq.util.quickcache import quickcache
from .models import Toggle


@quickcache(['slug', 'item', 'namespace'])
def toggle_enabled(slug, item, namespace=None):
    """
    Given a toggle and a username, whether the toggle is enabled for that user
    """
    item = namespaced_item(item, namespace)
    if not settings.UNIT_TESTING or getattr(settings, 'DB_ENABLED', True):
        try:
            toggle = Toggle.get(slug)
            return item in toggle.enabled_users
        except ResourceNotFound:
            return False


def set_toggle(slug, item, enabled, namespace=None):
    """
    Sets a toggle value explicitly. Should only save anything if the value needed to be changed.
    """
    if toggle_enabled(slug, item, namespace=namespace) != enabled:
        ns_item = namespaced_item(item, namespace)
        try:
            toggle_doc = Toggle.get(slug)
        except ResourceNotFound:
            toggle_doc = Toggle(slug=slug, enabled_users=[])
        if enabled:
            toggle_doc.add(ns_item)
        else:
            toggle_doc.remove(ns_item)
        from corehq.feature_previews import all_previews
        from corehq.toggles import all_toggles, NAMESPACE_DOMAIN
        static_toggles_by_slug = {t.slug: t for t in all_toggles() + all_previews()}
        if namespace == NAMESPACE_DOMAIN and slug in static_toggles_by_slug:
            static_toggle = static_toggles_by_slug[slug]
            if static_toggle.save_fn:
                static_toggle.save_fn(item, enabled)
        update_toggle_cache(slug, item, enabled, namespace)


def clear_toggle_cache(slug, item, namespace=None):
    toggle_enabled.clear(slug, item, namespace=namespace)


def update_toggle_cache(slug, item, state, namespace=None):
    clear_toggle_cache(slug, item, namespace)
    cache_key = toggle_enabled.get_cache_key(slug, item, namespace=namespace)
    cache.set(cache_key, state)


def namespaced_item(item, namespace):
    return '{namespace}:{item}'.format(
        namespace=namespace, item=item
    ) if namespace is not None else item


def parse_toggle(entry):
    """
    Split a toggle entry into the namespace an the item.
    :return: tuple(namespace, item)
    """
    from corehq.toggles import NAMESPACE_DOMAIN
    namespace = None
    if entry.startswith(NAMESPACE_DOMAIN):
        namespace, entry = entry.split(":")
    return namespace, entry


def find_users_with_toggle_enabled(toggle):
    from corehq.toggles import ALL_NAMESPACES, NAMESPACE_USER
    try:
        doc = Toggle.get(toggle.slug)
    except ResourceNotFound:
        return []
    prefixes = tuple(ns + ':' for ns in ALL_NAMESPACES if ns != NAMESPACE_USER)
    # Users are not prefixed with NAMESPACE_USER, but exclude NAMESPACE_USER to keep `prefixes` short
    return [u for u in doc.enabled_users if not u.startswith(prefixes)]


def find_domains_with_toggle_enabled(toggle):
    from corehq.toggles import NAMESPACE_DOMAIN
    try:
        doc = Toggle.get(toggle.slug)
    except ResourceNotFound:
        return []
    prefix = NAMESPACE_DOMAIN + ':'
    return [user[len(prefix):] for user in doc.enabled_users if user.startswith(prefix)]
