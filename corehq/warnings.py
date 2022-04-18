import os
import re
import warnings


def configure_warnings(is_testing):
    if is_testing:
        augment_warning_messages(is_testing)
        if 'PYTHONWARNINGS' not in os.environ:
            warnings.simplefilter("error")
    configure_deprecation_whitelist()


def configure_deprecation_whitelist():
    from django.utils.deprecation import RemovedInDjango41Warning
    from sqlalchemy.exc import SAWarning

    # warnings that may be resolved with a library upgrade
    config_apps = "|".join(re.escape(app) for app in [
        "captcha",
        "django_celery_results",
        "oauth2_provider",
        "statici18n",
        "two_factor",
    ])
    default_config_message = re.compile(fr"'.*({config_apps})' defines default_app_config")
    whitelist("captcha.fields", "ugettext_lazy() is deprecated")
    whitelist("celery", "'collections.abc'")
    whitelist("couchdbkit.schema.properties", "'collections.abc'")
    whitelist("django.apps", default_config_message, RemovedInDjango41Warning)
    whitelist("django_celery_results", "ugettext_lazy() is deprecated")
    whitelist("django_digest", "The 'warn' method is deprecated")
    whitelist("django_otp.plugins", "django.conf.urls.url() is deprecated")
    whitelist("kombu.utils.functional", "'collections.abc'")
    whitelist("logentry_admin.admin", "ugettext_lazy() is deprecated")
    whitelist("nose.importer", "the imp module is deprecated")
    whitelist("nose.util", "inspect.getargspec() is deprecated")
    whitelist("tastypie", "django.conf.urls.url() is deprecated")
    whitelist("tastypie", "request.is_ajax() is deprecated")

    # warnings that can be resolved with HQ code changes
    whitelist("", "json_response is deprecated.  Use django.http.JsonResponse instead.")
    whitelist("", "property_match are deprecated. Use boolean_expression instead.")
    whitelist("corehq.util.validation", "metaschema specified by $schema was not found")

    # other, resolution not obvious
    ignored_predicates = re.compile(r"^Predicate of partial index .* ignored during reflection")
    skipped_reflections = re.compile(
        "^Skipped unsupported reflection of expression-based index form_processor_xformattachmentsql_blobmeta_key")
    whitelist("sqlalchemy.", ignored_predicates, SAWarning)
    whitelist("sqlalchemy.", skipped_reflections, SAWarning)
    whitelist("unittest.case", "TestResult has no addExpectedFailure method", RuntimeWarning)


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

- Worse: add a targeted whitelist item to `corehq.warnings`
  `.configure_deprecation_whitelist()`. Whitelist items should target
  the specific module or package that triggers the warning, and should
  uniquely match the deprecation message so as not to hide other
  deprecation warnings in the same module or package.

- Last resort: if it is not possible to eliminate the deprecated code
  path or to add a whitelist item that uniquely matches the deprecation
  warning, use the `corehq.tests.util.warnings.filter_warnings()`
  decorator to filter the specific warning in tests that trigger it.
"""
