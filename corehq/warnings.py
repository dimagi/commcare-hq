import os
import re
import warnings

from django.utils.deprecation import RemovedInDjango41Warning
from sqlalchemy.exc import SAWarning


WHITELIST = [
    # Adding items here is a temporary workaround to prevent a warning
    # from causing tests to fail when the warning cannot be easily
    # avoided. There is a cost associated with adding items to this list
    # (the warnings module does a linear search through the list with
    # regex matching each time a warning is triggered), so it is best to
    # avoid it if possible.
    #
    # Item format:
    # (module_path, message_substring_or_regex, optional_warning_class, override_action)

    # warnings that may be resolved with a library upgrade
    ("captcha.fields", "ugettext_lazy() is deprecated"),
    ("couchdbkit.schema.properties", "'collections.abc'"),
    ("django.apps", re.compile(r"'(" + "|".join(re.escape(app) for app in [
        "captcha",
        "oauth2_provider",
        "statici18n",
        "two_factor",
    ]) + ")' defines default_app_config"), RemovedInDjango41Warning),
    ("nose.importer", "the imp module is deprecated"),
    ("nose.util", "inspect.getargspec() is deprecated"),
    ("pkg_resources", "pkg_resources.declare_namespace"),
    ("tastypie", "django.conf.urls.url() is deprecated"),
    ("tastypie", "request.is_ajax() is deprecated"),
    ("nose.suite", "'collections.abc'"),
    ("nose.plugins.collect", "'collections.abc'"),

    # warnings that can be resolved with HQ code changes
    ("", "json_response is deprecated.  Use django.http.JsonResponse instead."),
    ("", "property_match are deprecated. Use boolean_expression instead."),
    ("corehq.util.validation", "metaschema specified by $schema was not found"),
    ("corehq.apps.userreports.util", "'collections.abc'"),
    (
        # TODO: Removed this prior to the Elasticsearch upgrade. It is currently
        # needed due to the heavy use of 'pillowtop.es_utils.initialize_index[_and_mapping]'
        # in testing code, which is pending a future cleanup effort.
        "corehq.apps.es.index.settings",
        re.compile(r"Invalid index settings key .+, expected one of \["),
        UserWarning,
    ),
    (
        # This should be tested on a newer version(>2.5) of ES.Should be removed if fixed
        "elasticsearch5.connection.http_urllib3",
        "HTTPResponse.getheaders() is deprecated and will be removed in urllib3 v2.1.0."
    ),
    # Should be removed when Nose is updated
    ("nose.plugins.manager", "pkg_resources is deprecated as an API."),

    # other, resolution not obvious
    ("IPython.core.interactiveshell", "install IPython inside the virtualenv.", UserWarning),
    ("redis.connection", "distutils Version classes are deprecated. Use packaging.version instead."),
    ("sqlalchemy.", re.compile(r"^Predicate of partial index .* ignored during reflection"), SAWarning),
    ("sqlalchemy.",
        "Skipped unsupported reflection of expression-based index form_processor_xformattachmentsql_blobmeta_key",
        SAWarning),
    ("unittest.case", "TestResult has no addExpectedFailure method", RuntimeWarning),

    # warnings that should not be ignored
    # note: override_action "default" causes warning to be printed on stderr
    ("django.db.backends.postgresql.base", "unable to create a connection", RuntimeWarning, "default"),
]


def configure_warnings(is_testing):
    strict = is_testing or os.environ.get("CCHQ_STRICT_WARNINGS")
    if strict:
        augment_warning_messages()
        if 'PYTHONWARNINGS' not in os.environ:
            warnings.simplefilter("error")
    action = get_whitelist_action()
    if strict or "CCHQ_WHITELISTED_WARNINGS" in os.environ:
        for args in WHITELIST:
            whitelist(action, *args)


def whitelist(action, module, message, category=DeprecationWarning, override_action=None):
    """Whitelist warnings with matching criteria

    Similar to `warnings.filterwarnings` except `re.escape` `module`
    and `message`, and match `message` anywhere in the deprecation
    warning message.
    """
    if message:
        if isinstance(message, str):
            message = r".*" + re.escape(message)
        else:
            message = message.pattern
    warnings.filterwarnings(override_action or action, message, category, re.escape(module))


def get_whitelist_action():
    """Get the action for whitelisted warnings

    The warning action can be controlled with the environment variable
    `CCHQ_WHITELISTED_WARNINGS`. If that is not set, it falls back to
    the value of `PYTHONWARNINGS`, and if that is not set, 'ignore'.For
    example, to show warnings that would otherwise be ignored:

        export CCHQ_WHITELISTED_WARNINGS=default
    """
    default_action = os.environ.get("PYTHONWARNINGS", "ignore")
    action = os.environ.get("CCHQ_WHITELISTED_WARNINGS", default_action)
    if action not in ['default', 'always', 'ignore', 'module', 'once', 'error']:
        action = "ignore"  # happens when PYTHONWARNINGS has a complex value
    return action


def augment_warning_messages():
    """Make it easier to find the module that triggered the warning

    Adds additional context to each warning message, which is useful
    when adding new items to the whitelist:

        module: the.source.module.path line N

    Note: do not use in production since it adds overhead to the warning
    logic, which may be called frequently.
    """

    def augmented_warn(message, category=None, stacklevel=1, source=None):
        import sys
        # -- begin code copied from Python's warnings.py:warn --
        try:
            if stacklevel <= 1 or _is_internal_frame(sys._getframe(1)):
                # If frame is too small to care or if the warning originated in
                # internal code, then do not try to hide any frames.
                frame = sys._getframe(stacklevel)
            else:
                frame = sys._getframe(1)
                # Look for one frame less since the above line starts us off.
                for x in range(stacklevel - 1):
                    frame = _next_external_frame(frame)
                    if frame is None:
                        raise ValueError
        except ValueError:
            globals = sys.__dict__
            filename = "sys"
            lineno = 1
        else:
            globals = frame.f_globals
            filename = frame.f_code.co_filename
            lineno = frame.f_lineno
        if '__name__' in globals:
            module = globals['__name__']
        # -- end code copied from Python's warnings.py:warn --
        else:
            module = filename
        if not isinstance(message, str):
            category = category or message.__class__
            message = str(message)
        message += f"\nmodule: {module} line {lineno}"
        if category and issubclass(category, DeprecationWarning):
            message += POSSIBLE_RESOLUTIONS
            if os.environ.get("CCHQ_STRICT_WARNINGS") and os.environ.get('CCHQ_TESTING') != '1':
                message += STRICT_WARNINGS_WORKAROUND

        stacklevel += 1
        return real_warn(message, category, stacklevel, source)

    def _is_internal_frame(frame):
        """Signal whether the frame is an internal CPython implementation detail."""
        filename = frame.f_code.co_filename
        return 'importlib' in filename and '_bootstrap' in filename

    def _next_external_frame(frame):
        """Find the next frame that doesn't involve CPython internals."""
        frame = frame.f_back
        while frame is not None and _is_internal_frame(frame):
            frame = frame.f_back
        return frame

    real_warn = warnings.warn
    warnings.warn = augmented_warn


# Keep reference to orginal warn method so effects of
# augment_warning_messages can be unpatched if need be.
original_warn = warnings.warn


POSSIBLE_RESOLUTIONS = """

Possible resolutions:

- Best: Eliminate the deprecated code path.

- Worse: add an item to `corehq.warnings.WHITELIST`. Whitelist items
  should target the specific module or package that triggers the
  warning, and should uniquely match the deprecation message so as not
  to hide other deprecation warnings in the same module or package.

- Last resort: if it is not possible to eliminate the deprecated code
  path or to add a whitelist item that uniquely matches the deprecation
  warning, use the `corehq.tests.util.warnings.filter_warnings()`
  decorator to filter the specific warning in tests that trigger it.
"""

STRICT_WARNINGS_WORKAROUND = """
Workaround: prepend the command with 'env -u CCHQ_STRICT_WARNINGS ' to
disable strict warnings if none of these resolutions are appropriate.
"""
