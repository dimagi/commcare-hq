"""
This is a script intended to be run in a Django shell. It substitutes
invalid build versions in Application.built_with.version.

Context: https://dimagi.atlassian.net/browse/SAAS-18157
"""
from datetime import datetime
from typing import NamedTuple
from couchdbkit.exceptions import BadValueError
from corehq.apps.app_manager.models import Application, DeleteApplicationRecord
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


class AppTuple(NamedTuple):
    domain: str
    app_id: str
    copy_of: str  # Empty string for non-builds


def subs_app_versions(*, dry_run=True):
    print('Dry run' if dry_run else 'Live')
    modified = []
    apps = get_apps_with_bad_versions()
    for app_tuple in apps:
        modified.append(app_tuple)
        builds = get_builds_with_bad_versions(app_tuple.domain, app_tuple.app_id)
        modified.extend(builds)
        if not dry_run:
            subs_bad_version(app_tuple.app_id)
            for build_tuple in builds:
                subs_bad_version(build_tuple.app_id)
    print_table(modified)


def get_apps_with_bad_versions():
    bad_versions = list(VERSION_SUBSTITUTIONS.keys())
    apps = []
    for hit in (
        AppES()
        .doc_type('Application')
        .is_build(build=False)
        .OR(
            filters.term('build_spec.version', bad_versions),
            filters.term('built_with.version', bad_versions),
        )
        .run()
        .hits
    ):
        apps.append(AppTuple(hit['domain'], hit['doc_id'], ''))
    return apps


def get_builds_with_bad_versions(domain, app_id):
    bad_versions = list(VERSION_SUBSTITUTIONS.keys())
    builds = []
    for hit in (
        AppES()
        .doc_type('Application')
        .domain(domain)
        .app_id(app_id)  # copy_of
        .OR(
            filters.term('build_spec.version', bad_versions),
            filters.term('built_with.version', bad_versions),
        )
        .run()
        .hits
    ):
        builds.append(AppTuple(domain, hit['doc_id'], app_id))
    return builds


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
        app.save()
        print(f'{app_id} saved')
    except BadValueError:
        # App has multiple validation errors. (Invariably means that a
        # form has been stored as a string and not JSON.)
        delete_app(app_dict)
        print(f'{app_id} deleted')


def delete_app(app_dict):
    # See ApplicationBase.delete_app()
    app_dict['doc_type'] += '-Deleted'
    Application.get_db().save_doc(app_dict)
    record = DeleteApplicationRecord(
        domain=app_dict['domain'],
        app_id=app_dict['_id'],
        datetime=datetime.utcnow()
    )
    record.save()


def print_table(app_tuples):
    if not app_tuples:
        return
    print('Affected apps:\n')
    print('| Domain       | App ID                           | Copy of                          |')
    print('| ------------ | -------------------------------- | -------------------------------- |')
    for domain, app_id, copy_of in app_tuples:
        print(f'| {domain:<12} | {app_id:<32} | {copy_of:<32} |')


subs_app_versions()
