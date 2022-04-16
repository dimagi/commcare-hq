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
    """Whitelist warnings with matching criteria

    Similar to `warnings.filterwarnings` except `re.escape` `module`
    and `message`, and match `message` anywhere in the deprecation
    warning message.

    The warning action can be controlled with the environment variable
    `CCHQ_WHITELISTED_WARNINGS`. If that is not set, it falls back to
    the value of `PYTHONWARNINGS`, and if that is not set, 'ignore'.For
    example, to show warnings that would otherwise be ignored:

        export CCHQ_WHITELISTED_WARNINGS=default
    """
    msg = r".*" + re.escape(message)
    default_action = os.environ.get("PYTHONWARNINGS", "ignore")
    action = os.environ.get("CCHQ_WHITELISTED_WARNINGS", default_action)
    warnings.filterwarnings(action, msg, category, re.escape(module))
