# coding=utf-8
from __future__ import absolute_import, unicode_literals

from io import open
import json
import logging
import os
import re
import six
from lxml import etree
from memoized import memoized

from collections import defaultdict
from django.conf import settings
from django_prbac.exceptions import PermissionDenied
from django.utils.translation import ugettext as _

from corehq import privileges
from corehq.util.timer import time_method
from corehq.util import view_utils

from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.app_manager.const import (
    AUTO_SELECT_CASE,
    AUTO_SELECT_FIXTURE,
    AUTO_SELECT_RAW,
    AUTO_SELECT_USER,
    WORKFLOW_FORM,
    WORKFLOW_PARENT_MODULE,
)
from corehq.apps.app_manager.exceptions import (
    AppEditingError,
    CaseXPathValidationError,
    FormNotFoundException,
    LocationXpathValidationError,
    ModuleIdMissingException,
    ModuleNotFoundException,
    PracticeUserException,
    SuiteValidationError,
    UserCaseXPathValidationError,
    XFormException,
    XFormValidationError,
    XFormValidationFailed,
)
from corehq.apps.app_manager.util import (
    app_callout_templates,
    module_case_hierarchy_has_circular_reference,
    split_path,
    xpath_references_case,
    xpath_references_user_case,
)
from corehq.apps.app_manager.xform import parse_xml as _parse_xml
from corehq.apps.app_manager.xpath import interpolate_xpath, LocationXpath
from corehq.apps.app_manager.xpath_validator import validate_xpath
from corehq.apps.domain.models import Domain


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
        if self.app.build_spec.supports_j2me() and hasattr(self.app, 'profile'):
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
    def __init__(self, module):
        self.module = module

    def get_module_info(self):
        return {
            'id': self.module.id,
            'name': self.module.name,
            'unique_id': self.module.unique_id,
        }

    def validate_for_build(self):
        '''
        This is a wrapper for the actual validation logic, in order to gracefully capture exceptions
        caused by modules missing (parent modules, source modules, etc). Subclasses should not override.
        '''
        errors = []
        try:
            errors += self.validate_with_raise()
        except ModuleNotFoundException as ex:
            errors.append({
                "type": "missing module",
                "message": six.text_type(ex),
                "module": self.get_module_info(),
            })

        return errors

    def validate_with_raise(self):
        '''
        This is the real validation logic, to be overridden/augmented by subclasses.
        '''
        errors = []
        needs_case_detail = self.module.requires_case_details()
        needs_case_type = needs_case_detail or any(f.is_registration_form() for f in self.module.get_forms())
        if needs_case_detail or needs_case_type:
            errors.extend(self.module.validator.get_case_errors(
                needs_case_type=needs_case_type,
                needs_case_detail=needs_case_detail
            ))
        if self.module.case_list_form.form_id:
            try:
                form = self.module.get_app().get_form(self.module.case_list_form.form_id)
            except FormNotFoundException:
                errors.append({
                    'type': 'case list form missing',
                    'module': self.get_module_info()
                })
            else:
                if not form.is_registration_form(self.module.case_type):
                    errors.append({
                        'type': 'case list form not registration',
                        'module': self.get_module_info(),
                        'form': form,
                    })
        if self.module.module_filter:
            is_valid, message = validate_xpath(self.module.module_filter)
            if not is_valid:
                errors.append({
                    'type': 'module filter has xpath error',
                    'xpath_error': message,
                    'module': self.get_module_info(),
                })

        return errors

    def validate_detail_columns(self, columns):
        from corehq.apps.app_manager.suite_xml.const import FIELD_TYPE_LOCATION
        from corehq.apps.locations.util import parent_child
        from corehq.apps.locations.fixtures import should_sync_hierarchical_fixture

        hierarchy = None
        for column in columns:
            if column.field_type == FIELD_TYPE_LOCATION:
                domain = self.module.get_app().domain
                domain_obj = Domain.get_by_name(domain)
                try:
                    if not should_sync_hierarchical_fixture(domain_obj, self.module.get_app()):
                        # discontinued feature on moving to flat fixture format
                        raise LocationXpathValidationError(
                            _('That format is no longer supported. To reference the location hierarchy you need to'
                              ' use the "Custom Calculations in Case List" feature preview. For more information '
                              'see: https://confluence.dimagi.com/pages/viewpage.action?pageId=38276915'))
                    hierarchy = hierarchy or parent_child(domain)
                    LocationXpath('').validate(column.field_property, hierarchy)
                except LocationXpathValidationError as e:
                    yield {
                        'type': 'invalid location xpath',
                        'details': six.text_type(e),
                        'module': self.get_module_info(),
                        'column': column,
                    }


class ModuleDetailValidatorMixin(object):
    '''
    Validation logic common to basic and shadow modules, which both have detail configuration.
    '''
    def validate_details_for_build(self):
        errors = []
        for sort_element in self.module.detail_sort_elements:
            try:
                self._validate_detail_screen_field(sort_element.field)
            except ValueError:
                errors.append({
                    'type': 'invalid sort field',
                    'field': sort_element.field,
                    'module': self.get_module_info(),
                })
        if self.module.case_list_filter:
            try:
                # test filter is valid, while allowing for advanced user hacks like "foo = 1][bar = 2"
                case_list_filter = interpolate_xpath('dummy[' + self.module.case_list_filter + ']')
                etree.XPath(case_list_filter)
            except (etree.XPathSyntaxError, CaseXPathValidationError):
                errors.append({
                    'type': 'invalid filter xpath',
                    'module': self.get_module_info(),
                    'filter': self.module.case_list_filter,
                })
        for detail in [self.module.case_details.short, self.module.case_details.long]:
            if detail.use_case_tiles:
                if not detail.display == "short":
                    errors.append({
                        'type': "invalid tile configuration",
                        'module': self.get_module_info(),
                        'reason': _('Case tiles may only be used for the case list (not the case details).')
                    })
                col_by_tile_field = {c.case_tile_field: c for c in detail.columns}
                for field in ["header", "top_left", "sex", "bottom_left", "date"]:
                    if field not in col_by_tile_field:
                        errors.append({
                            'type': "invalid tile configuration",
                            'module': self.get_module_info(),
                            'reason': _('A case property must be assigned to the "{}" tile field.'.format(field))
                        })
        return errors

    def get_case_errors(self, needs_case_type, needs_case_detail, needs_referral_detail=False):
        module_info = self.get_module_info()

        if needs_case_type and not self.module.case_type:
            yield {
                'type': 'no case type',
                'module': module_info,
            }

        if needs_case_detail:
            if not self.module.case_details.short.columns:
                yield {
                    'type': 'no case detail',
                    'module': module_info,
                }
            columns = self.module.case_details.short.columns + self.module.case_details.long.columns
            errors = self.validate_detail_columns(columns)
            for error in errors:
                yield error

        if needs_referral_detail and not self.module.ref_details.short.columns:
            yield {
                'type': 'no ref detail',
                'module': module_info,
            }

    def _validate_detail_screen_field(self, field):
        # If you change here, also change here:
        # corehq/apps/app_manager/static/app_manager/js/details/screen_config.js
        field_re = r'^([a-zA-Z][\w_-]*:)*([a-zA-Z][\w_-]*/)*#?[a-zA-Z][\w_-]*$'
        if not re.match(field_re, field):
            raise ValueError("Invalid Sort Field")


class ModuleValidator(ModuleBaseValidator, ModuleDetailValidatorMixin):
    def validate_with_raise(self):
        errors = super(ModuleValidator, self).validate_with_raise()
        errors += self.validate_details_for_build()
        if not self.module.forms and not self.module.case_list.show:
            errors.append({
                'type': 'no forms or case list',
                'module': self.get_module_info(),
            })

        if module_case_hierarchy_has_circular_reference(self.module):
            errors.append({
                'type': 'circular case hierarchy',
                'module': self.get_module_info(),
            })

        if self.module.root_module and self.module.root_module.is_training_module:
            errors.append({
                'type': 'training module parent',
                'module': self.get_module_info(),
            })

        if self.module.root_module and self.module.is_training_module:
            errors.append({
                'type': 'training module child',
                'module': self.get_module_info(),
            })

        return errors


class AdvancedModuleValidator(ModuleBaseValidator):
    def validate_with_raise(self):
        errors = super(AdvancedModuleValidator, self).validate_with_raise()
        if not self.module.forms and not self.module.case_list.show:
            errors.append({
                'type': 'no forms or case list',
                'module': self.get_module_info(),
            })
        if self.module.case_list_form.form_id:
            forms = self.module.get_forms()

            case_tag = None
            loaded_case_types = None
            for form in forms:
                info = self.get_module_info()
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
                            non_auto_select_actions[index - 1].case_tag and
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

                if case_action and case_action.details_module != self.module.unique_id:
                    errors.append({
                        'type': 'forms in case list module must use modules details',
                        'module': info,
                        'form': form_info,
                    })

        return errors

    def get_case_errors(self, needs_case_type, needs_case_detail, needs_referral_detail=False):
        module_info = self.get_module_info()

        if needs_case_type and not self.module.case_type:
            yield {
                'type': 'no case type',
                'module': module_info,
            }

        if needs_case_detail:
            if not self.module.case_details.short.columns:
                yield {
                    'type': 'no case detail',
                    'module': module_info,
                }
            if self.module.get_app().commtrack_enabled and not self.module.product_details.short.columns:
                for form in self.module.get_forms():
                    if self.module.case_list.show or \
                            any(action.show_product_stock for action in form.actions.load_update_cases):
                        yield {
                            'type': 'no product detail',
                            'module': module_info,
                        }
                        break
            columns = self.module.case_details.short.columns + self.module.case_details.long.columns
            if self.module.get_app().commtrack_enabled:
                columns += self.module.product_details.short.columns
            errors = self.validate_detail_columns(columns)
            for error in errors:
                yield error


class ReportModuleValidator(ModuleBaseValidator):
    def validate_with_raise(self):
        errors = super(ReportModuleValidator, self).validate_with_raise()
        if not self.module.check_report_validity().is_valid:
            errors.append({
                'type': 'report config ref invalid',
                'module': self.get_module_info()
            })
        elif not self.module.reports:
            errors.append({
                'type': 'no reports',
                'module': self.get_module_info(),
            })
        if self._has_duplicate_instance_ids():
            errors.append({
                'type': 'report config id duplicated',
                'module': self.get_module_info(),
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


class ShadowModuleValidator(ModuleBaseValidator, ModuleDetailValidatorMixin):
    def validate_with_raise(self):
        errors = super(ShadowModuleValidator, self).validate_with_raise()
        errors += self.validate_details_for_build()
        if not self.module.source_module:
            errors.append({
                'type': 'no source module id',
                'module': self.get_module_info()
            })
        return errors


@memoized
def load_case_reserved_words():
    with open(
        os.path.join(os.path.dirname(__file__), '..', 'static', 'app_manager', 'json', 'case-reserved-words.json'),
        encoding='utf-8'
    ) as f:
        return json.load(f)


def validate_property(property, allow_parents=True):
    """
    Validate a case property name

    >>> validate_property('parent/maternal-grandmother_fullName')
    >>> validate_property('foo+bar')
    Traceback (most recent call last):
      ...
    ValueError: Invalid Property

    """
    if allow_parents:
        # this regex is also copied in propertyList.ejs
        regex = r'^[a-zA-Z][\w_-]*(/[a-zA-Z][\w_-]*)*$'
    else:
        regex = r'^[a-zA-Z][\w_-]*$'
    if not re.match(regex, property):
        raise ValueError("Invalid Property")


class FormBaseValidator(object):
    def __init__(self, form):
        self.form = form

    def validate_for_build(self, validate_module):
        errors = []

        try:
            module = self.form.get_module()
        except AttributeError:
            module = None

        meta = {
            'form_type': self.form.form_type,
            'module': module.validator.get_module_info() if module else {},
            'form': {
                "id": self.form.id if hasattr(self.form, 'id') else None,
                "name": self.form.name,
                'unique_id': self.form.unique_id,
            }
        }

        xml_valid = False
        if self.form.source == '' and self.form.form_type != 'shadow_form':
            errors.append(dict(type="blank form", **meta))
        else:
            try:
                _parse_xml(self.form.source)
                xml_valid = True
            except XFormException as e:
                errors.append(dict(
                    type="invalid xml",
                    message=six.text_type(e) if self.form.source else '',
                    **meta
                ))
            except ValueError:
                logging.error("Failed: _parse_xml(string=%r)" % self.form.source)
                raise

        try:
            questions = self.form.cached_get_questions()
        except XFormException as e:
            error = {'type': 'validation error', 'validation_message': six.text_type(e)}
            error.update(meta)
            errors.append(error)

        if not errors:
            has_questions = any(not q.get('is_group') for q in questions)
            if not has_questions and self.form.form_type != 'shadow_form':
                errors.append(dict(type="blank form", **meta))
            else:
                try:
                    self.form.validate_form()
                except XFormValidationError as e:
                    error = {'type': 'validation error', 'validation_message': six.text_type(e)}
                    error.update(meta)
                    errors.append(error)
                except XFormValidationFailed:
                    pass  # ignore this here as it gets picked up in other places

        if self.form.post_form_workflow == WORKFLOW_FORM:
            if not self.form.form_links:
                errors.append(dict(type="no form links", **meta))
            for form_link in self.form.form_links:
                try:
                    self.form.get_app().get_form(form_link.form_id)
                except FormNotFoundException:
                    errors.append(dict(type='bad form link', **meta))
        elif self.form.post_form_workflow == WORKFLOW_PARENT_MODULE:
            if not module.root_module:
                errors.append(dict(type='form link to missing root', **meta))

        # this isn't great but two of FormBase's subclasses have form_filter
        if hasattr(self.form, 'form_filter') and self.form.form_filter:
            with self.form.timing_context("validate_xpath"):
                is_valid, message = validate_xpath(self.form.form_filter, allow_case_hashtags=True)
            if not is_valid:
                error = {
                    'type': 'form filter has xpath error',
                    'xpath_error': message,
                }
                error.update(meta)
                errors.append(error)

        errors.extend(self.extended_build_validation(meta, xml_valid, validate_module))

        return errors

    def extended_build_validation(self, error_meta, xml_valid, validate_module=True):
        """
        Override to perform additional validation during build process.
        """
        return []


class IndexedFormBaseValidator(FormBaseValidator):
    @property
    def timing_context(self):
        return self.form.get_app().timing_context

    def check_case_properties(self, all_names=None, subcase_names=None, case_tag=None):
        all_names = all_names or []
        subcase_names = subcase_names or []
        errors = []

        reserved_words = load_case_reserved_words()
        for key in all_names:
            try:
                validate_property(key)
            except ValueError:
                errors.append({'type': 'update_case word illegal', 'word': key, 'case_tag': case_tag})
            _, key = split_path(key)
            if key in reserved_words:
                errors.append({'type': 'update_case uses reserved word', 'word': key, 'case_tag': case_tag})

        # no parent properties for subcase
        for key in subcase_names:
            if not re.match(r'^[a-zA-Z][\w_-]*$', key):
                errors.append({'type': 'update_case word illegal', 'word': key, 'case_tag': case_tag})

        return errors

    def check_paths(self, paths):
        errors = []
        try:
            questions = self.form.cached_get_questions()
            valid_paths = {question['value']: question['tag'] for question in questions}
        except XFormException as e:
            errors.append({'type': 'invalid xml', 'message': six.text_type(e)})
        else:
            no_multimedia = not self.form.get_app().enable_multimedia_case_property
            for path in set(paths):
                if path not in valid_paths:
                    errors.append({'type': 'path error', 'path': path})
                elif no_multimedia and valid_paths[path] == "upload":
                    errors.append({'type': 'multimedia case property not supported', 'path': path})

        return errors


class FormValidator(IndexedFormBaseValidator):
    def check_actions(self):
        errors = []

        subcase_names = set()
        for subcase_action in self.form.actions.subcases:
            if not subcase_action.case_type:
                errors.append({'type': 'subcase has no case type'})

            subcase_names.update(subcase_action.case_properties)

        if self.form.requires == 'none' and self.form.actions.open_case.is_active() \
                and not self.form.actions.open_case.name_path:
            errors.append({'type': 'case_name required'})

        errors.extend(self.check_case_properties(
            all_names=self.form.actions.all_property_names(),
            subcase_names=subcase_names
        ))

        def generate_paths():
            from corehq.apps.app_manager.models import FormAction
            for action in self.form.active_actions().values():
                if isinstance(action, list):
                    actions = action
                else:
                    actions = [action]
                for action in actions:
                    for path in FormAction.get_action_paths(action):
                        yield path

        errors.extend(self.check_paths(generate_paths()))

        return errors

    @time_method()
    def extended_build_validation(self, error_meta, xml_valid, validate_module=True):
        errors = []
        if xml_valid:
            for error in self.check_actions():
                error.update(error_meta)
                errors.append(error)

        if validate_module:
            needs_case_type = False
            needs_case_detail = False
            needs_referral_detail = False

            if self.form.requires_case():
                needs_case_detail = True
                needs_case_type = True
            if self.form.requires_case_type():
                needs_case_type = True
            if self.form.requires_referral():
                needs_referral_detail = True

            errors.extend(self.form.get_module().validator.get_case_errors(
                needs_case_type=needs_case_type,
                needs_case_detail=needs_case_detail,
                needs_referral_detail=needs_referral_detail,
            ))

        return errors


class AdvancedFormValidator(IndexedFormBaseValidator):
    def check_actions(self):
        errors = []

        from corehq.apps.app_manager.models import AdvancedOpenCaseAction, LoadUpdateAction

        case_tags = list(self.form.actions.get_case_tags())
        for action in self.form.actions.get_subcase_actions():
            for case_index in action.case_indices:
                if case_index.tag not in case_tags:
                    errors.append({'type': 'missing parent tag', 'case_tag': case_index.tag})
                if case_index.relationship == 'question' and not case_index.relationship_question:
                    errors.append({'type': 'missing relationship question', 'case_tag': case_index.tag})

            if isinstance(action, AdvancedOpenCaseAction):
                if not action.name_path:
                    errors.append({'type': 'case_name required', 'case_tag': action.case_tag})

                for case_index in action.case_indices:
                    meta = self.form.actions.actions_meta_by_tag.get(case_index.tag)
                    if meta and meta['type'] == 'open' and meta['action'].repeat_context:
                        if (
                            not action.repeat_context or
                            not action.repeat_context.startswith(meta['action'].repeat_context)
                        ):
                            errors.append({'type': 'subcase repeat context',
                                           'case_tag': action.case_tag,
                                           'parent_tag': case_index.tag})

            errors.extend(self.check_case_properties(
                subcase_names=action.get_property_names(),
                case_tag=action.case_tag
            ))

        for action in self.form.actions.get_all_actions():
            if not action.case_type and (not isinstance(action, LoadUpdateAction) or not action.auto_select):
                errors.append({'type': "no case type in action", 'case_tag': action.case_tag})

            if isinstance(action, LoadUpdateAction) and action.auto_select:
                mode = action.auto_select.mode
                if not action.auto_select.value_key:
                    key_names = {
                        AUTO_SELECT_CASE: _('Case property'),
                        AUTO_SELECT_FIXTURE: _('Lookup Table field'),
                        AUTO_SELECT_USER: _('custom user property'),
                        AUTO_SELECT_RAW: _('custom XPath expression'),
                    }
                    if mode in key_names:
                        errors.append({'type': 'auto select key', 'key_name': key_names[mode]})

                if not action.auto_select.value_source:
                    source_names = {
                        AUTO_SELECT_CASE: _('Case tag'),
                        AUTO_SELECT_FIXTURE: _('Lookup Table tag'),
                    }
                    if mode in source_names:
                        errors.append({'type': 'auto select source', 'source_name': source_names[mode]})
                elif mode == AUTO_SELECT_CASE:
                    case_tag = action.auto_select.value_source
                    if not self.form.actions.get_action_from_tag(case_tag):
                        errors.append({'type': 'auto select case ref', 'case_tag': action.case_tag})

            errors.extend(self.check_case_properties(
                all_names=action.get_property_names(),
                case_tag=action.case_tag
            ))

        if self.form.form_filter:
            # Replace any dots with #case, which doesn't make for valid xpath
            # but will trigger any appropriate validation errors
            interpolated_form_filter = interpolate_xpath(self.form.form_filter, case_xpath="#case",
                    module=self.form.get_module(), form=self.form)

            form_filter_references_case = (
                xpath_references_case(interpolated_form_filter) or
                xpath_references_user_case(interpolated_form_filter)
            )

            if form_filter_references_case:
                if not any(action for action in self.form.actions.load_update_cases if not action.auto_select):
                    errors.append({'type': "filtering without case"})

        def generate_paths():
            for action in self.form.actions.get_all_actions():
                for path in action.get_paths():
                    yield path

            if self.form.schedule:
                if self.form.schedule.transition_condition.type == 'if':
                    yield self.form.schedule.transition_condition.question
                if self.form.schedule.termination_condition.type == 'if':
                    yield self.form.schedule.termination_condition.question

        errors.extend(self.check_paths(generate_paths()))

        return errors

    @time_method()
    def extended_build_validation(self, error_meta, xml_valid, validate_module=True):
        errors = []
        if xml_valid:
            for error in self.check_actions():
                error.update(error_meta)
                errors.append(error)

        module = self.form.get_module()
        if validate_module:
            errors.extend(module.validator.get_case_errors(
                needs_case_type=False,
                needs_case_detail=module.requires_case_details(),
                needs_referral_detail=False,
            ))

        return errors


class ShadowFormValidator(IndexedFormBaseValidator):
    @time_method()
    def extended_build_validation(self, error_meta, xml_valid, validate_module=True):
        errors = super(ShadowFormValidator, self).extended_build_validation(error_meta, xml_valid, validate_module)
        if not self.form.shadow_parent_form_id:
            error = {
                "type": "missing shadow parent",
            }
            error.update(error_meta)
            errors.append(error)
        elif not self.form.shadow_parent_form:
            error = {
                "type": "shadow parent does not exist",
            }
            error.update(error_meta)
            errors.append(error)
        return errors

    def check_actions(self):
        errors = super(ShadowFormValidator, self).check_actions()

        shadow_parent_form = self.form.shadow_parent_form
        if shadow_parent_form:
            case_tags = set(self.form.extra_actions.get_case_tags())
            missing_tags = []
            for action in shadow_parent_form.actions.load_update_cases:
                if action.case_tag not in case_tags:
                    missing_tags.append(action.case_tag)
            if missing_tags:
                errors.append({'type': 'missing shadow parent tag', 'case_tags': missing_tags})
        return errors
