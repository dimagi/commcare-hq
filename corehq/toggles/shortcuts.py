from couchdbkit import ResourceNotFound
from django.conf import settings

from .models import Toggle


def toggle_enabled(slug, item, namespace=None):
    """
    Given a toggle and a username, whether the toggle is enabled for that user
    """
    from corehq.toggles import NAMESPACE_EMAIL_DOMAIN
    if namespace == NAMESPACE_EMAIL_DOMAIN and '@' in item:
        item = item.split('@')[-1]

    item = namespaced_item(item, namespace)
    if not settings.UNIT_TESTING or getattr(settings, 'DB_ENABLED', True):
        toggle = Toggle.cached_get(slug)
        return item in toggle.enabled_users if toggle else False


def set_toggle(slug, item, enabled, namespace=None):
    if _set_toggle_without_clear_cache(slug, item, enabled, namespace=namespace):
        from corehq.apps.toggle_ui.views import clear_toggle_cache_by_namespace
        clear_toggle_cache_by_namespace(namespace, item)
        return True


def set_toggles(slugs, item, enabled, namespace=None):
    toggle_changed = False
    for slug in slugs:
        if _set_toggle_without_clear_cache(slug, item, enabled, namespace):
            toggle_changed = True
    if toggle_changed:
        from corehq.apps.toggle_ui.views import clear_toggle_cache_by_namespace
        clear_toggle_cache_by_namespace(namespace, item)


def _set_toggle_without_clear_cache(slug, item, enabled, namespace=None):
    """
    Sets a toggle value explicitly. Should only save anything if the value needed to be changed.
    """
    if toggle_enabled(slug, item, namespace=namespace) == enabled:
        return False

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
    return True


def namespaced_item(item, namespace):
    return '{namespace}:{item}'.format(
        namespace=namespace, item=item
    ) if namespace is not None else item


def parse_toggle(entry):
    """
    Split a toggle entry into the namespace an the item.
    :return: tuple(namespace, item)
    """
    from corehq.toggles import NAMESPACE_DOMAIN, NAMESPACE_EMAIL_DOMAIN
    namespace = None
    if entry.startswith((NAMESPACE_DOMAIN + ':', NAMESPACE_EMAIL_DOMAIN + ':')):
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
