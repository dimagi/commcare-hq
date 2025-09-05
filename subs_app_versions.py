"""
This is a script intended to be run in a Django shell. It substitutes
invalid build versions in Application.built_with.version.

Context: https://dimagi.atlassian.net/browse/SAAS-18157
"""
from couchdbkit.exceptions import BadValueError
from corehq.apps.app_manager.models import Application
from corehq.apps.builds.models import SemanticVersionProperty
from corehq.apps.es import filters
from corehq.apps.es.apps import AppES

VERSION_SUBSTITUTIONS = {
    # From https://github.com/dimagi/commcare-hq/pull/20845
    '1.2.dev': '1.2.999',
    '1.2.0alpha': '1.2.998',
    '1.3.0alpha': '1.3.999',
    '2.25.w': '2.25.999',
}
APP_IDS = [
    # (domain, app_id)
    # Output from previous runs
]


def subs_app_versions(*, dry_run=True):
    print('Dry run' if dry_run else 'Live')
    modified = []
    for domain, app_id in APP_IDS:
        for hit in (
            AppES()
            .doc_type('Application')
            .domain(domain)
            .app_id(app_id)  # copy_of
            .OR(
                filters.NOT(filters.empty('build_spec.version')),
                filters.NOT(filters.empty('built_with.version')),
            )
            .scroll()
        ):
            if (
                not is_version_ok(get_by_path(hit, ('build_spec', 'version')))
                or not is_version_ok(get_by_path(hit, ('built_with', 'version')))
            ):
                modified.append((hit['domain'], hit['doc_id'], hit['copy_of']))
                if not dry_run:
                    subs_bad_version(hit['doc_id'])
    print_table(modified)


def is_version_ok(version):
    try:
        SemanticVersionProperty().validate(version)
        return True
    except BadValueError:
        return False


def get_by_path(dict_, path):
    """
    Get a value from a nested dictionary using an Iterable of keys as the path.

    >>> some_dict = {'foo': {'bar': 1}}
    >>> other_dict = {'foo': {'baz': 2}}
    >>> get_by_path(some_dict, ('foo', 'bar'))
    1
    >>> get_by_path(other_dict, ('foo', 'bar'))
    None
    """
    current = dict_
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def subs_bad_version(app_id):
    app_dict = Application.get_db().get(app_id)
    build_spec_ver = get_by_path(app_dict, ('build_spec', 'version'))
    if not is_version_ok(build_spec_ver):
        subs = VERSION_SUBSTITUTIONS[build_spec_ver]
        app_dict['build_spec']['version'] = subs
    built_with_ver = get_by_path(app_dict, ('built_with', 'version'))
    if not is_version_ok(built_with_ver):
        subs = VERSION_SUBSTITUTIONS[built_with_ver]
        app_dict['built_with']['version'] = subs
    try:
        app = Application.wrap(app_dict)
    except BadValueError as err:
        print(f"Skipping {app_dict['domain']} | {app_id}:\n{err}\n")
        return
    app.save()


def print_table(app_id_tuples):
    if not app_id_tuples:
        return
    print('Affected apps:\n')
    print('| Domain       | App ID                           | Copy of                          |')
    print('| ------------ | -------------------------------- | -------------------------------- |')
    for domain, app_id, copy_of in app_id_tuples:
        print(f'| {domain:<12} | {app_id:<32} | {copy_of:<32} |')


subs_app_versions()
