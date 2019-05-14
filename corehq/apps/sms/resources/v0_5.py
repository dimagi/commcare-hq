from __future__ import absolute_import
from __future__ import unicode_literals
import json
from collections import namedtuple
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.api.resources import HqBaseResource
from corehq.apps.api.resources.auth import RequirePermissionAuthentication
from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.domain.models import Domain
from corehq.apps.sms.mixin import apply_leniency
from corehq.apps.sms.models import SelfRegistrationInvitation
from corehq.apps.users.models import Permissions
from corehq.util.python_compatibility import soft_assert_type_text
from corehq import privileges
from django.http import HttpResponse, Http404
from tastypie.exceptions import ImmediateHttpResponse
from tastypie.validation import Validation
import six

FieldDefinition = namedtuple('FieldDefinition', 'name required type')


class SelfRegistrationApiException(Exception):
    pass


class SelfRegistrationValidationException(Exception):
    def __init__(self, errors):
        self.errors = errors
        super(SelfRegistrationValidationException, self).__init__('')


class SelfRegistrationUserInfo(object):

    def __eq__(self, other):
        """
        Allow comparison of two of these objects for use in tests.
        """
        if isinstance(other, self.__class__):
            return all(
                [getattr(self, prop) == getattr(other, prop)
                 for prop in ('phone_number', 'custom_user_data')]
            )

        return False

    def __ne__(self, other):
        return not self.__eq__(other)

    __hash__ = None

    def __init__(self, phone_number, custom_user_data=None):
        self.phone_number = phone_number
        self.custom_user_data = custom_user_data


class SelfRegistrationInfo(object):
    def __init__(self, app_id, android_only=False, require_email=False, custom_registration_message=None):
        self.app_id = app_id
        self.android_only = android_only
        self.require_email = require_email
        self.custom_registration_message = custom_registration_message
        self.users = []

    def add_user(self, user_info):
        """
        :param user_info: should be an instance of SelfRegistrationUserInfo
        """
        self.users.append(user_info)


class SelfRegistrationReinstallInfo(object):

    def __init__(self, app_id, reinstall_message=None):
        self.app_id = app_id
        if isinstance(reinstall_message, six.string_types):
            soft_assert_type_text(reinstall_message)
            self.reinstall_message = reinstall_message.strip()
        else:
            self.reinstall_message = None
        self.users = []

    def add_user(self, user_info):
        """
        :param user_info: should be an instance of SelfRegistrationUserInfo
        """
        self.users.append(user_info)


class BaseUserSelfRegistrationValidation(Validation):

    def _validate_toplevel_fields(self, data, field_defs):
        """
        :param data: any dictionary of data
        :param field_defs: a list of FieldDefinition namedtuples representing the names
        and types of the fields to validate
        """
        for field_def in field_defs:
            if field_def.name not in data and field_def.required:
                raise SelfRegistrationValidationException(
                    {field_def.name: 'This field is required'}
                )

            if field_def.name in data:
                if isinstance(data[field_def.name], six.string_types):
                    soft_assert_type_text(data[field_def.name])
                if not isinstance(data[field_def.name], field_def.type):
                    if isinstance(field_def.type, tuple):
                        if len(field_def.type) > 1:
                            raise SelfRegistrationValidationException(
                                {field_def.name: 'Expected type in {}'.format(
                                    ', '.join(t.__name__ for t in field_def.type)
                                )}
                            )
                        else:
                            type_name = field_def.type[0].__name__
                    else:
                        type_name = field_def.type.__name__
                    raise SelfRegistrationValidationException(
                        {field_def.name: 'Expected type: {}'.format(type_name)}
                    )

    def _validate_app_id(self, domain, app_id):
        try:
            get_app(domain, app_id, latest=True)
        except Http404:
            raise SelfRegistrationValidationException({'app_id': 'Invalid app_id specified'})

    def _validate_users(self, user_data):
        phone_numbers = set()
        for user_info in user_data:
            if not isinstance(user_info, dict):
                raise SelfRegistrationValidationException(
                    {'users': 'Expected a list of dictionaries'}
                )

            self._validate_toplevel_fields(user_info, [
                FieldDefinition('phone_number', True, six.string_types),
                FieldDefinition('custom_user_data', False, dict),
            ])

            phone_number = apply_leniency(user_info['phone_number'])
            if phone_number in phone_numbers:
                raise SelfRegistrationValidationException(
                    {'users': 'phone_number cannot be reused within a request: {}'.format(phone_number)}
                )
            phone_numbers.add(phone_number)

    def is_valid(self, bundle, request=None):
        raise NotImplementedError()


class UserSelfRegistrationValidation(BaseUserSelfRegistrationValidation):

    def is_valid(self, bundle, request=None):
        if not request:
            raise SelfRegistrationApiException('Expected request to be present')

        try:
            self._validate_toplevel_fields(bundle.data, [
                FieldDefinition('app_id', True, six.string_types),
                FieldDefinition('users', True, list),
                FieldDefinition('android_only', False, bool),
                FieldDefinition('require_email', False, bool),
                FieldDefinition('custom_registration_message', False, six.string_types),
            ])

            self._validate_app_id(request.domain, bundle.data['app_id'])
            self._validate_users(bundle.data['users'])
        except SelfRegistrationValidationException as e:
            return e.errors

        return {}


class UserSelfRegistrationReinstallValidation(BaseUserSelfRegistrationValidation):

    def is_valid(self, bundle, request=None):
        if not request:
            raise SelfRegistrationApiException('Expected request to be present')

        try:
            self._validate_toplevel_fields(bundle.data, [
                FieldDefinition('app_id', True, six.string_types),
                FieldDefinition('users', True, list),
                FieldDefinition('reinstall_message', False, six.string_types),
            ])

            self._validate_app_id(request.domain, bundle.data['app_id'])
            self._validate_users(bundle.data['users'])
        except SelfRegistrationValidationException as e:
            return e.errors

        return {}


class BaseUserSelfRegistrationResource(HqBaseResource):

    def dispatch(self, request_type, request, **kwargs):
        domain_obj = Domain.get_by_name(request.domain)

        if not domain_has_privilege(domain_obj, privileges.INBOUND_SMS):
            raise ImmediateHttpResponse(
                HttpResponse(
                    json.dumps({'error': 'Your current plan does not have access to this feature'}),
                    content_type='application/json',
                    status=401
                )
            )
        elif not domain_obj.sms_mobile_worker_registration_enabled:
            raise ImmediateHttpResponse(
                HttpResponse(
                    json.dumps({'error': 'Please first enable SMS mobile worker registration for your project.'}),
                    content_type='application/json',
                    status=403
                )
            )
        else:
            return super(BaseUserSelfRegistrationResource, self).dispatch(request_type, request, **kwargs)

    def detail_uri_kwargs(self, bundle_or_obj):
        return {}


class UserSelfRegistrationResource(BaseUserSelfRegistrationResource):
    """
    Used to initiate the mobile worker self-registration workflow over SMS.
    """

    def __init__(self, *args, **kwargs):
        super(UserSelfRegistrationResource, self).__init__(*args, **kwargs)
        self.registration_result = None

    class Meta(object):
        authentication = RequirePermissionAuthentication(Permissions.edit_data)
        resource_name = 'sms_user_registration'
        allowed_methods = ['post']
        validation = UserSelfRegistrationValidation()

    def full_hydrate(self, bundle):
        if not self.is_valid(bundle):
            raise ImmediateHttpResponse(response=self.error_response(bundle.request, bundle.errors))

        data = bundle.data

        custom_registration_message = data.get('custom_registration_message')
        if isinstance(custom_registration_message, six.string_types):
            soft_assert_type_text(custom_registration_message)
            custom_registration_message = custom_registration_message.strip()
            if not custom_registration_message:
                custom_registration_message = None

        obj = SelfRegistrationInfo(
            data.get('app_id'),
            data.get('android_only', False),
            data.get('require_email', False),
            custom_registration_message
        )
        for user_info in data.get('users', []):
            obj.add_user(SelfRegistrationUserInfo(
                user_info.get('phone_number'),
                user_info.get('custom_user_data')
            ))
        bundle.obj = obj
        return bundle

    def obj_create(self, bundle, **kwargs):
        bundle = self.full_hydrate(bundle)
        self.registration_result = SelfRegistrationInvitation.initiate_workflow(
            bundle.request.domain,
            bundle.obj.users,
            app_id=bundle.obj.app_id,
            custom_first_message=bundle.obj.custom_registration_message,
            android_only=bundle.obj.android_only,
            require_email=bundle.obj.require_email,
        )
        return bundle

    def post_list(self, request, **kwargs):
        super(UserSelfRegistrationResource, self).post_list(request, **kwargs)
        success_numbers, invalid_format_numbers, numbers_in_use = self.registration_result

        return HttpResponse(
            json.dumps({
                'success_numbers': success_numbers,
                'invalid_format_numbers': invalid_format_numbers,
                'numbers_in_use': numbers_in_use,
            }),
            content_type='application/json',
        )


class UserSelfRegistrationReinstallResource(BaseUserSelfRegistrationResource):
    """
    Used to resend the CommCare install link to a user's phone.
    """

    def __init__(self, *args, **kwargs):
        super(UserSelfRegistrationReinstallResource, self).__init__(*args, **kwargs)
        self.reinstall_result = None

    class Meta(object):
        authentication = RequirePermissionAuthentication(Permissions.edit_data)
        resource_name = 'sms_user_registration_reinstall'
        allowed_methods = ['post']
        validation = UserSelfRegistrationReinstallValidation()

    def full_hydrate(self, bundle):
        if not self.is_valid(bundle):
            raise ImmediateHttpResponse(response=self.error_response(bundle.request, bundle.errors))

        data = bundle.data

        obj = SelfRegistrationReinstallInfo(
            data.get('app_id'),
            data.get('reinstall_message')
        )
        for user_info in data.get('users', []):
            obj.add_user(SelfRegistrationUserInfo(
                user_info.get('phone_number')
            ))
        bundle.obj = obj
        return bundle

    def obj_create(self, bundle, **kwargs):
        bundle = self.full_hydrate(bundle)
        self.reinstall_result = SelfRegistrationInvitation.send_install_link(
            bundle.request.domain,
            bundle.obj.users,
            bundle.obj.app_id,
            custom_message=bundle.obj.reinstall_message
        )
        return bundle

    def post_list(self, request, **kwargs):
        super(UserSelfRegistrationReinstallResource, self).post_list(request, **kwargs)
        success_numbers, invalid_format_numbers, error_numbers = self.reinstall_result

        return HttpResponse(
            json.dumps({
                'success_numbers': success_numbers,
                'invalid_format_numbers': invalid_format_numbers,
                'error_numbers': error_numbers,
            }),
            content_type='application/json',
        )
