from .exceptions import ESRegistryError


def register_alias(alias, info):
    """Register an Elasticsearch index or alias name (add it to this module's
    `ES_META` dict).

    :param alias: Elasticsearch index or alias name
    :param info: index metadata
    :raises: ESRegistryError
    """
    if alias in ES_META:
        raise ESRegistryError(f"alias is already registered: {alias}")
    ES_META[alias] = info


def deregister_alias(alias):
    """Deregister a previously registered alias (remove it from this module's
    `ES_META` dict).

    :param alias: existing (registered) Elasticsearch index or alias name
    :raises: ESRegistryError
    """
    try:
        del ES_META[alias]
    except KeyError:
        raise ESRegistryError(f"alias is not registered: {alias}")


def verify_registered_alias(alias):
    """Check if provided alias is valid (registered).

    :param alias: Elasticsearch index or alias name
    :raises: ESRegistryError
    """
    all_aliases = set(m.alias for m in ES_META.values())
    if alias not in all_aliases:
        raise ESRegistryError(f"invalid alias {alias!r}, expected one of "
                              f"{sorted(all_aliases)}")


# global ES alias metadata registry
ES_META = {}
