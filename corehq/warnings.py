import os
import re
import warnings


def configure_warnings(is_testing):
    if is_testing and 'PYTHONWARNINGS' not in os.environ:
        warnings.simplefilter("error")
    configure_deprecation_whitelist()


def configure_deprecation_whitelist():
    # warnings that may be resolved with a library upgrade
    whitelist("celery", "'collections.abc'")
    whitelist("couchdbkit.schema.properties", "'collections.abc'")
    whitelist("kombu.utils.functional", "'collections.abc'")
    whitelist("nose.importer", "the imp module is deprecated")

    # warnings that can be resolved with HQ code changes
    whitelist("corehq.util.validation", "metaschema specified by $schema was not found")


def whitelist(module, message, category=DeprecationWarning):
    msg = r".*" + re.escape(message)
    warnings.filterwarnings("default", msg, category, re.escape(module))
