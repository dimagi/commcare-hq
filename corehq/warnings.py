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
    # (module_path, message_substring_or_regex, optional_warning_class)

    # warnings that may be resolved with a library upgrade
    ("captcha.fields", "ugettext_lazy() is deprecated"),
    ("celery", "'collections.abc'"),
    ("compressor.filters.base", "smart_text() is deprecated"),
    ("compressor.signals", "The providing_args argument is deprecated."),
    ("couchdbkit.schema.properties", "'collections.abc'"),
    ("django.apps", re.compile(r"'(" + "|".join(re.escape(app) for app in [
        "captcha",
        "django_celery_results",
        "oauth2_provider",
        "statici18n",
        "two_factor",
    ]) + ")' defines default_app_config"), RemovedInDjango41Warning),
    ("django_celery_results", "ugettext_lazy() is deprecated"),
    ("django_otp.plugins", "django.conf.urls.url() is deprecated"),
    ("kombu.utils.functional", "'collections.abc'"),
    ("logentry_admin.admin", "ugettext_lazy() is deprecated"),
    ("nose.importer", "the imp module is deprecated"),
    ("nose.util", "inspect.getargspec() is deprecated"),
    ("tastypie", "django.conf.urls.url() is deprecated"),
    ("tastypie", "request.is_ajax() is deprecated"),

    # warnings that can be resolved with HQ code changes
    ("", "json_response is deprecated.  Use django.http.JsonResponse instead."),
    ("", "property_match are deprecated. Use boolean_expression instead."),
    ("corehq.util.validation", "metaschema specified by $schema was not found"),

    # other, resolution not obvious
    ("sqlalchemy.", re.compile(r"^Predicate of partial index .* ignored during reflection"), SAWarning),
    ("sqlalchemy.",
        "Skipped unsupported reflection of expression-based index form_processor_xformattachmentsql_blobmeta_key",
        SAWarning),
    ("unittest.case", "TestResult has no addExpectedFailure method", RuntimeWarning),
]


def configure_warnings(is_testing):
    strict = is_testing or os.environ.get("CCHQ_STRICT_WARNINGS")
    if strict:
        augment_warning_messages(is_testing)
        if 'PYTHONWARNINGS' not in os.environ:
            warnings.simplefilter("error")
    if strict or "CCHQ_WHITELISTED_WARNINGS" in os.environ:
        for args in WHITELIST:
            whitelist(*args)


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
    if message:
        if isinstance(message, str):
            message = r".*" + re.escape(message)
        else:
            message = message.pattern
    default_action = os.environ.get("PYTHONWARNINGS", "ignore")
    action = os.environ.get("CCHQ_WHITELISTED_WARNINGS", default_action)
    warnings.filterwarnings(action, message, category, re.escape(module))


def augment_warning_messages(is_testing):
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
        message += f"\nmodule: {module} line {lineno}"

        if is_testing:
            message += POSSIBLE_RESOLUTIONS

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
