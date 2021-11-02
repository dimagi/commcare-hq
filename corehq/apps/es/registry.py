"""Maintain and interact with the global Elasticsearch "info object" registry.

    The API provided by this module replaces the previously public `ES_META`
dictionary and implements controls to serve all the purposes that that
dictionary was used for.

    The original (and current main) purpose of the registry is to ensure that
Elasticsearch indices are not referenced by their raw _index name_ by enforcing
that only _alias names_ get used to perform Elasticsearch requests. Index info
registry items are keyed by pseudo-aliases, or "canonical names", which are only
defined in code and may differ from the _actual alias name_ for that index (e.g.
"forms" instead of "xforms").

    The registry also serves the purpose of being the authoritative source of
index metadata information for non-index-specific code which needs to perform
Elasticsearch requests. Some examples include:

- Django management commands that need to query Elasticsearch by canonical name.
- Elasticsearch cluster management utilities.
- Elasticsearch interface and tests.
"""

from corehq.util.test_utils import unit_testing_only

from .exceptions import ESRegistryError


def register(info, cname=None):
    """Register an Elasticsearch index info object.

    :param info: index info object
    :param cname: (optional) register index info as canonical name `cname`
                  instead of default (`info.alias`)
    :raises: ESRegistryError
    """
    alias = info.alias
    if cname is None:
        cname = alias
    if cname in _ES_INFO_REGISTRY:
        raise ESRegistryError(f"name {cname!r} is already registered")
    _ES_INFO_REGISTRY[cname] = info
    if alias in _ALIAS_REF_COUNTS:
        _ALIAS_REF_COUNTS[alias] += 1
    else:
        _ALIAS_REF_COUNTS[alias] = 1
    return cname


@unit_testing_only
def deregister(info_or_cname):
    """Deregister a previously registered index. For testing only (production
    code never deregisters indices).

    :param info_or_cname: index info object or canonical name used for
                          an existing registry entry
    :raises: ESRegistryError
    """
    cname = getattr(info_or_cname, "alias", info_or_cname)
    try:
        info = _ES_INFO_REGISTRY.pop(cname)
    except KeyError:
        raise ESRegistryError(f"name {cname!r} is not registered")
    _ALIAS_REF_COUNTS[info.alias] -= 1
    if _ALIAS_REF_COUNTS[info.alias] < 1:
        del _ALIAS_REF_COUNTS[info.alias]


def verify_alias(alias):
    """Check if provided alias is valid (alias of a registered index).

    :param alias: index alias to check in registry
    :raises: ESRegistryError
    """
    if alias not in _ALIAS_REF_COUNTS:
        raise ESRegistryError(f"invalid index alias {alias!r}, expected one "
                              f"of {sorted(_ALIAS_REF_COUNTS)}")


def verify_registered(info_or_cname):
    """Check if registry exists for an index.

    :param info_or_cname: index info object or canonical name
    :raises: ESRegistryError
    """
    cname = getattr(info_or_cname, "alias", info_or_cname)
    if cname not in _ES_INFO_REGISTRY:
        raise ESRegistryError(f"invalid registry name {cname!r}, expected one "
                              f"of {sorted(_ES_INFO_REGISTRY)}")


def registry_entry(cname):
    """Get the index info object registered for a canonical name.

    :param cname: canonical name of existing registry entry
    :returns: index info object
    :raises: ESRegistryError
    """
    try:
        return _ES_INFO_REGISTRY[cname]
    except KeyError:
        raise ESRegistryError(f"invalid registry name {cname!r}, expected one "
                              f"of {sorted(_ES_INFO_REGISTRY)}")


def get_registry():
    """Get a copy of the registry.

    :returns: dict
    """
    return _ES_INFO_REGISTRY.copy()


# global ES index and alias registries
_ES_INFO_REGISTRY = {}
_ALIAS_REF_COUNTS = {}
