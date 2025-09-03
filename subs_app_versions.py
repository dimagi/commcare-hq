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


def subs_app_versions():
    for hit in (
        AppES()
        .doc_type('Application')
        .is_build(build=False)
        .NOT(filters.empty('built_with.version'))
        .scroll()
    ):
        version = hit['built_with']['version']
        if not is_version_ok(version):
            print('.', end='')
            subs_bad_version(hit['doc_id'], version)
    print()


def is_version_ok(version):
    try:
        SemanticVersionProperty().validate(version)
        return True
    except BadValueError:
        return False


def subs_bad_version(app_id, version):
    subs = VERSION_SUBSTITUTIONS[version]  # Raise KeyError on unknown version
    app_dict = Application.get_db().get(app_id)
    app_dict['built_with']['version'] = subs
    app = Application.wrap(app_dict)
    app.save()


subs_app_versions()
