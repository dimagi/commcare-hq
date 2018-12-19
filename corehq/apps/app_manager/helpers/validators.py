# coding=utf-8
from __future__ import absolute_import, unicode_literals

import six

from collections import defaultdict
from django.conf import settings
from django_prbac.exceptions import PermissionDenied
from django.utils.translation import ugettext as _

from dimagi.utils.logging import notify_exception

from corehq import privileges
from corehq.util.timer import time_method
from corehq.util import view_utils

from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.app_manager.exceptions import (
    AppEditingError,
    CaseXPathValidationError,
    UserCaseXPathValidationError,
    ModuleIdMissingException,
    PracticeUserException,
    SuiteValidationError,
    XFormException,
    XFormValidationError,
)
from corehq.apps.app_manager.util import app_callout_templates


class ApplicationBaseValidator(object):
    def __init__(self, app, *args, **kwargs):
        super(ApplicationBaseValidator, self).__init__(*args, **kwargs)
        self.app = app
        self.domain = app.domain

    @property
    def timing_context(self):
        return self.app.timing_context

    def validate_app(self):
        errors = []

        errors.extend(self._check_password_charset())

        try:
            self._validate_fixtures()
            self._validate_intents()
            self._validate_practice_users()
            if not errors:
                self.app.create_all_files()
        except CaseXPathValidationError as cve:
            errors.append({
                'type': 'invalid case xpath reference',
                'module': cve.module,
                'form': cve.form,
            })
        except UserCaseXPathValidationError as ucve:
            errors.append({
                'type': 'invalid user property xpath reference',
                'module': ucve.module,
                'form': ucve.form,
            })
        except PracticeUserException as pue:
            errors.append({
                'type': 'practice user config error',
                'message': six.text_type(pue),
                'build_profile_id': pue.build_profile_id,
            })
        except (AppEditingError, XFormValidationError, XFormException,
                PermissionDenied, SuiteValidationError) as e:
            errors.append({'type': 'error', 'message': six.text_type(e)})
        except Exception as e:
            if settings.DEBUG:
                raise

            # this is much less useful/actionable without a URL
            # so make sure to include the request
            notify_exception(view_utils.get_request(), "Unexpected error building app")
            errors.append({'type': 'error', 'message': 'unexpected error: %s' % e})
        return errors

    @time_method()
    def _validate_fixtures(self):
        if not domain_has_privilege(self.domain, privileges.LOOKUP_TABLES):
            # remote apps don't support get_forms yet.
            # for now they can circumvent the fixture limitation. sneaky bastards.
            if hasattr(self.app, 'get_forms'):
                for form in self.app.get_forms():
                    if form.has_fixtures:
                        raise PermissionDenied(_(
                            "Usage of lookup tables is not supported by your "
                            "current subscription. Please upgrade your "
                            "subscription before using this feature."
                        ))

    @time_method()
    def _validate_intents(self):
        if domain_has_privilege(self.domain, privileges.CUSTOM_INTENTS):
            return

        if hasattr(self.app, 'get_forms'):
            for form in self.app.get_forms():
                intents = form.wrapped_xform().odk_intents
                if intents:
                    if not domain_has_privilege(self.domain, privileges.TEMPLATED_INTENTS):
                        raise PermissionDenied(_(
                            "Usage of integrations is not supported by your "
                            "current subscription. Please upgrade your "
                            "subscription before using this feature."
                        ))
                    else:
                        templates = next(app_callout_templates)
                        if len(set(intents) - set(t['id'] for t in templates)):
                            raise PermissionDenied(_(
                                "Usage of external integration is not supported by your "
                                "current subscription. Please upgrade your "
                                "subscription before using this feature."
                            ))

    @time_method()
    def _validate_practice_users(self):
        # validate practice_mobile_worker of app and all app profiles
        # raises PracticeUserException in case of misconfiguration
        if not self.app.enable_practice_users:
            return
        self.app.get_practice_user()
        try:
            for build_profile_id in self.app.build_profiles:
                self.app.get_practice_user(build_profile_id)
        except PracticeUserException as e:
            e.build_profile_id = build_profile_id
            raise e

    def _check_password_charset(self):
        errors = []
        if hasattr(self.app, 'profile'):
            password_format = self.app.profile.get('properties', {}).get('password_format', 'n')
            message = _(
                'Your app requires {0} passwords but the admin password is not '
                '{0}. To resolve, go to app settings, Advanced Settings, Java '
                'Phone General Settings, and reset the Admin Password to '
                'something that is {0}'
            )

            if password_format == 'n' and self.app.admin_password_charset in 'ax':
                errors.append({'type': 'password_format',
                               'message': message.format('numeric')})
            if password_format == 'a' and self.app.admin_password_charset in 'x':
                errors.append({'type': 'password_format',
                               'message': message.format('alphanumeric')})
        return errors


class ApplicationValidator(ApplicationBaseValidator):
    @time_method()
    def validate_app(self):
        errors = []

        for lang in self.app.langs:
            if not lang:
                errors.append({'type': 'empty lang'})

        errors.extend(self._check_modules())
        errors.extend(self._check_forms())

        if any(not module.unique_id for module in self.app.get_modules()):
            raise ModuleIdMissingException
        modules_dict = {m.unique_id: m for m in self.app.get_modules()}

        def _parent_select_fn(module):
            if hasattr(module, 'parent_select') and module.parent_select.active:
                return module.parent_select.module_id

        if self._has_dependency_cycle(modules_dict, _parent_select_fn):
            errors.append({'type': 'parent cycle'})

        errors.extend(self._child_module_errors(modules_dict))
        errors.extend(self._check_subscription())

        # Call super's validation last because it involves calling create_all_files
        errors.extend(super(ApplicationValidator, self).validate_app())

        return errors

    @time_method()
    def _check_modules(self):
        errors = []
        if not self.app.modules:
            errors.append({'type': "no modules"})
        for module in self.app.get_modules():
            errors.extend(module.validate_for_build())
        return errors

    @time_method()
    def _check_forms(self):
        from corehq.apps.app_manager.models import ShadowForm

        errors = []
        xmlns_count = defaultdict(int)
        for form in self.app.get_forms():
            errors.extend(form.validate_for_build(validate_module=False))

            # make sure that there aren't duplicate xmlns's
            if not isinstance(form, ShadowForm):
                xmlns_count[form.xmlns] += 1
            for xmlns in xmlns_count:
                if xmlns_count[xmlns] > 1:
                    errors.append({'type': "duplicate xmlns", "xmlns": xmlns})
        return errors

    def _has_dependency_cycle(self, modules, neighbour_id_fn):
        """
        Detect dependency cycles given modules and the neighbour_id_fn

        :param modules: A mapping of module unique_ids to Module objects
        :neighbour_id_fn: function to get the neibour module unique_id
        :return: True if there is a cycle in the module relationship graph
        """
        visited = set()
        completed = set()

        def cycle_helper(m):
            if m.id in visited:
                if m.id in completed:
                    return False
                return True
            visited.add(m.id)
            parent = modules.get(neighbour_id_fn(m), None)
            if parent is not None and cycle_helper(parent):
                return True
            completed.add(m.id)
            return False
        for module in modules.values():
            if cycle_helper(module):
                return True
        return False

    def _child_module_errors(self, modules_dict):
        module_errors = []

        def _root_module_fn(module):
            if hasattr(module, 'root_module_id'):
                return module.root_module_id

        if self._has_dependency_cycle(modules_dict, _root_module_fn):
            module_errors.append({'type': 'root cycle'})

        module_ids = set([m.unique_id for m in self.app.get_modules()])
        root_ids = set([_root_module_fn(m) for m in self.app.get_modules() if _root_module_fn(m) is not None])
        if not root_ids.issubset(module_ids):
            module_errors.append({'type': 'unknown root'})
        return module_errors

    def _check_subscription(self):

        def app_uses_usercase(app):
            return any(m.uses_usercase() for m in app.get_modules())

        errors = []
        if app_uses_usercase(self.app) and not domain_has_privilege(self.domain, privileges.USER_CASE):
            errors.append({
                'type': 'subscription',
                'message': _('Your application is using User Properties and your current subscription does not '
                             'support that. You can remove User Properties functionality by opening the User '
                             'Properties tab in a form that uses it, and clicking "Remove User Properties".'),
            })
        return errors
