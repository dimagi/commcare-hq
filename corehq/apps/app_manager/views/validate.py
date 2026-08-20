"""GET API to validate an application or form.

Both endpoints run the same checks the "Validate" build button runs, and
return the same structured error dicts the underlying validators produce
(``type``, ``message``, etc.) rather than inventing a parallel error
vocabulary for every existing validation failure.
"""
from dataclasses import dataclass, field

from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import View

from corehq.apps.api.decorators import api_throttle
from corehq.apps.app_manager.views.single_form_api import (
    get_app_for_api,
    get_form_for_api,
)
from corehq.apps.app_manager.views.base_api import errors_response
from corehq.apps.domain.decorators import api_auth
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import HqPermissions
from corehq.util.view_utils import json_error


@dataclass
class ValidationResult:
    valid: bool
    validation_errors: list = field(default_factory=list)

    def to_json(self):
        # Not dataclasses.asdict(): validation_errors are opaque validator
        # dicts that may nest jsonobject containers asdict can't reconstruct.
        return {'valid': self.valid, 'validation_errors': self.validation_errors}


@method_decorator(csrf_exempt, name='dispatch')
@method_decorator(json_error, name='dispatch')
@method_decorator(api_throttle, name='dispatch')
class AppValidateApiView(View):
    """GET whether an application is valid, and its build errors if not."""

    @method_decorator(require_permission(HqPermissions.view_apps, login_decorator=api_auth()))
    def get(self, request, domain, app_id):
        app, error = get_app_for_api(domain, app_id)
        if error:
            return errors_response(error)

        errors = app.validate_app()
        return JsonResponse(ValidationResult(not errors, errors).to_json())


@method_decorator(csrf_exempt, name='dispatch')
@method_decorator(json_error, name='dispatch')
@method_decorator(api_throttle, name='dispatch')
class FormValidateApiView(View):
    """GET whether a single form is valid, and its build errors if not."""

    @method_decorator(require_permission(HqPermissions.view_apps, login_decorator=api_auth()))
    def get(self, request, domain, app_id, module_id, form_id):
        form, result = get_form_for_api(domain, app_id, module_id, form_id)
        if not result.success:
            return errors_response(result)

        errors = form.validate_for_build()
        return JsonResponse(ValidationResult(not errors, errors).to_json())
