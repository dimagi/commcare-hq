# coding=utf-8
from __future__ import absolute_import, unicode_literals

import six
from lxml import etree

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
    FormNotFoundException,
    UserCaseXPathValidationError,
    ModuleIdMissingException,
    ModuleNotFoundException,
    PracticeUserException,
    SuiteValidationError,
    XFormException,
    XFormValidationError,
)
from corehq.apps.app_manager.util import app_callout_templates, module_case_hierarchy_has_circular_reference
from corehq.apps.app_manager.xpath import interpolate_xpath
from corehq.apps.app_manager.xpath_validator import validate_xpath


class ApplicationBaseValidator(object):
    def __init__(self, app, *args, **kwargs):
        super(ApplicationBaseValidator, self).__init__(*args, **kwargs)
        self.app = app
        self.domain = app.domain

    @property
    def timing_context(self):
        return self.app.timing_context

    def validate_app(self, existing_errors=None):
        errors = existing_errors or []

        errors.extend(self._check_password_charset())
        errors.extend(self._validate_fixtures())
        errors.extend(self._validate_intents())
        errors.extend(self._validate_practice_users())

        try:
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
                        return [{
                            'type': 'error',
                            'message': _(
                                "Usage of lookup tables is not supported by your "
                                "current subscription. Please upgrade your "
                                "subscription before using this feature."
                            ),
                        }]
        return []

    @time_method()
    def _validate_intents(self):
        if domain_has_privilege(self.domain, privileges.CUSTOM_INTENTS):
            return []

        if hasattr(self.app, 'get_forms'):
            for form in self.app.get_forms():
                intents = form.wrapped_xform().odk_intents
                if intents:
                    if not domain_has_privilege(self.domain, privileges.TEMPLATED_INTENTS):
                        return [{
                            'type': 'error',
                            'message': _(
                                "Usage of integrations is not supported by your "
                                "current subscription. Please upgrade your "
                                "subscription before using this feature."
                            ),
                        }]
                    else:
                        templates = next(app_callout_templates)
                        if len(set(intents) - set(t['id'] for t in templates)):
                            return [{
                                'type': 'error',
                                'message': _(
                                    "Usage of external integration is not supported by your "
                                    "current subscription. Please upgrade your "
                                    "subscription before using this feature."
                                ),
                            }]
            return []

    @time_method()
    def _validate_practice_users(self):
        # validate practice_mobile_worker of app and all app profiles
        # raises PracticeUserException in case of misconfiguration
        if not self.app.enable_practice_users:
            return []
        try:
            build_profile_id = None
            self.app.get_practice_user()
            for build_profile_id in self.app.build_profiles:
                self.app.get_practice_user(build_profile_id)
        except PracticeUserException as e:
            return [{
                'type': 'practice user config error',
                'message': six.text_type(e),
                'build_profile_id': build_profile_id,
            }]
        return []

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
    def validate_app(self, existing_errors=None):
        errors = existing_errors or []

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
        errors = super(ApplicationValidator, self).validate_app(errors)

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


class ModuleBaseValidator(object):
    def __init__(self, module, *args, **kwargs):
        super(ModuleBaseValidator, self).__init__(*args, **kwargs)
        self.module = module

    def validate_for_build(self):
        errors = []
        try:
            errors += self.module.validate_with_raise()
        except ModuleNotFoundException as ex:
            errors.append({
                "type": "missing module",
                "message": six.text_type(ex),
                "module": self.module.get_module_info(),
            })

        return errors

    def validate_with_raise(self):
        errors = []
        needs_case_detail = self.module.requires_case_details()
        needs_case_type = needs_case_detail or len([1 for f in self.module.get_forms() if f.is_registration_form()])
        if needs_case_detail or needs_case_type:
            errors.extend(self.module.get_case_errors(
                needs_case_type=needs_case_type,
                needs_case_detail=needs_case_detail
            ))
        if self.module.case_list_form.form_id:
            try:
                form = self.module.get_app().get_form(self.module.case_list_form.form_id)
            except FormNotFoundException:
                errors.append({
                    'type': 'case list form missing',
                    'module': self.module.get_module_info()
                })
            else:
                if not form.is_registration_form(self.module.case_type):
                    errors.append({
                        'type': 'case list form not registration',
                        'module': self.module.get_module_info(),
                        'form': form,
                    })
        if self.module.module_filter:
            is_valid, message = validate_xpath(self.module.module_filter)
            if not is_valid:
                errors.append({
                    'type': 'module filter has xpath error',
                    'xpath_error': message,
                    'module': self.module.get_module_info(),
                })

        return errors


class ModuleDetailValidatorMixin(object):
    def validate_details_for_build(self):
        errors = []
        for sort_element in self.module.detail_sort_elements:
            try:
                validate_detail_screen_field(sort_element.field)
            except ValueError:
                errors.append({
                    'type': 'invalid sort field',
                    'field': sort_element.field,
                    'module': self.module.get_module_info(),
                })
        if self.module.case_list_filter:
            try:
                # test filter is valid, while allowing for advanced user hacks like "foo = 1][bar = 2"
                case_list_filter = interpolate_xpath('dummy[' + self.module.case_list_filter + ']')
                etree.XPath(case_list_filter)
            except (etree.XPathSyntaxError, CaseXPathValidationError):
                errors.append({
                    'type': 'invalid filter xpath',
                    'module': self.module.get_module_info(),
                    'filter': self.module.case_list_filter,
                })
        for detail in [self.module.case_details.short, self.module.case_details.long]:
            if detail.use_case_tiles:
                if not detail.display == "short":
                    errors.append({
                        'type': "invalid tile configuration",
                        'module': self.module.get_module_info(),
                        'reason': _('Case tiles may only be used for the case list (not the case details).')
                    })
                col_by_tile_field = {c.case_tile_field: c for c in detail.columns}
                for field in ["header", "top_left", "sex", "bottom_left", "date"]:
                    if field not in col_by_tile_field:
                        errors.append({
                            'type': "invalid tile configuration",
                            'module': self.module.get_module_info(),
                            'reason': _('A case property must be assigned to the "{}" tile field.'.format(field))
                        })
        return errors


class ModuleValidator(ModuleDetailValidatorMixin):
    def __init__(self, module, *args, **kwargs):
        super(ModuleValidator, self).__init__(*args, **kwargs)
        self.module = module

    def validate_with_raise(self):
        errors = self.validate_details_for_build()
        if not self.module.forms and not self.module.case_list.show:
            errors.append({
                'type': 'no forms or case list',
                'module': self.module.get_module_info(),
            })

        if module_case_hierarchy_has_circular_reference(self.module):
            errors.append({
                'type': 'circular case hierarchy',
                'module': self.module.get_module_info(),
            })

        if self.module.root_module and self.module.root_module.is_training_module:
            errors.append({
                'type': 'training module parent',
                'module': self.module.get_module_info(),
            })

        if self.module.root_module and self.module.is_training_module:
            errors.append({
                'type': 'training module child',
                'module': self.module.get_module_info(),
            })

        return errors


class AdvancedModuleValidator(object):
    def __init__(self, module, *args, **kwargs):
        super(AdvancedModuleValidator, self).__init__(*args, **kwargs)
        self.module = module

    def validate_with_raise(self):
        errors = []
        if not self.module.forms and not self.module.case_list.show:
            errors.append({
                'type': 'no forms or case list',
                'module': self.module.get_module_info(),
            })
        if self.module.case_list_form.form_id:
            forms = self.module.forms

            case_tag = None
            loaded_case_types = None
            for form in forms:
                info = self.module.get_module_info()
                form_info = {"id": form.id if hasattr(form, 'id') else None, "name": form.name}
                non_auto_select_actions = [a for a in form.actions.load_update_cases if not a.auto_select]
                this_forms_loaded_case_types = {action.case_type for action in non_auto_select_actions}
                if loaded_case_types is None:
                    loaded_case_types = this_forms_loaded_case_types
                elif loaded_case_types != this_forms_loaded_case_types:
                    errors.append({
                        'type': 'all forms in case list module must load the same cases',
                        'module': info,
                        'form': form_info,
                    })

                if not non_auto_select_actions:
                    errors.append({
                        'type': 'case list module form must require case',
                        'module': info,
                        'form': form_info,
                    })
                elif len(non_auto_select_actions) != 1:
                    for index, action in reversed(list(enumerate(non_auto_select_actions))):
                        if (
                            index > 0 and
                            non_auto_select_actions[index - 1].case_tag not in (p.tag for p in action.case_indices)
                        ):
                            errors.append({
                                'type': 'case list module form can only load parent cases',
                                'module': info,
                                'form': form_info,
                            })

                case_action = non_auto_select_actions[-1] if non_auto_select_actions else None
                if case_action and case_action.case_type != self.module.case_type:
                    errors.append({
                        'type': 'case list module form must match module case type',
                        'module': info,
                        'form': form_info,
                    })

                # set case_tag if not already set
                case_tag = case_action.case_tag if not case_tag and case_action else case_tag
                if case_action and case_action.case_tag != case_tag:
                    errors.append({
                        'type': 'all forms in case list module must have same case management',
                        'module': info,
                        'form': form_info,
                        'expected_tag': case_tag
                    })

                if case_action and case_action.details_module and case_action.details_module != self.module.unique_id:
                    errors.append({
                        'type': 'forms in case list module must use modules details',
                        'module': info,
                        'form': form_info,
                    })

        return errors


class ReportModuleValidator(object):
    def __init__(self, module, *args, **kwargs):
        super(ReportModuleValidator, self).__init__(*args, **kwargs)
        self.module = module

    def validate_with_raise(self):
        errors = []
        if not self.module.check_report_validity().is_valid:
            errors.append({
                'type': 'report config ref invalid',
                'module': self.module.get_module_info()
            })
        elif not self.module.reports:
            errors.append({
                'type': 'no reports',
                'module': self.module.get_module_info(),
            })
        if self._has_duplicate_instance_ids():
            errors.append({
                'type': 'report config id duplicated',
                'module': self.module.get_module_info(),
            })
        return errors

    def _has_duplicate_instance_ids(self):
        from corehq.apps.app_manager.suite_xml.features.mobile_ucr import get_uuids_by_instance_id
        duplicate_instance_ids = {
            instance_id
            for instance_id, uuids in get_uuids_by_instance_id(self.module.get_app().domain).items()
            if len(uuids) > 1
        }
        return any(report_config.instance_id in duplicate_instance_ids
                   for report_config in self.module.report_configs)


class ShadowModuleValidator(ModuleDetailValidatorMixin):
    def __init__(self, module, *args, **kwargs):
        super(ShadowModuleValidator, self).__init__(*args, **kwargs)
        self.module = module

    def validate_with_raise(self):
        errors = self.validate_details_for_build()
        if not self.module.source_module:
            errors.append({
                'type': 'no source module id',
                'module': self.module.get_module_info()
            })
        return errors
