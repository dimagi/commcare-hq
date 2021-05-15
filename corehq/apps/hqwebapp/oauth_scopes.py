import json
import os
from collections import defaultdict

from oauth2_provider.scopes import BaseScopes

from corehq.apps.domain.utils import get_domain_from_url
from corehq.motech.fhir.const import FHIR_VERSION_4_0_1
from corehq.motech.fhir.models import FHIRResourceType, get_schema_dir

DEFAULT_SMART_SCOPES = {
    'launch/patient': 'Access your unique patient ID',
    'offline_access': 'Maintain access to your data when you are offline',
    'online_access': 'Maintain access to your data when you are online',
}

HQ_DEFINED_SCOPES = {
    'access_apis': 'Access API data on all your CommCare projects',
}


class FhirScopeBuilder():
    CLIENT_TYPES = [('patient', 'your patients\''), ('user', 'your')]
    ACCESS_PERMISSIONS = [('read', 'Read'), ('write', 'Write'), ('*', 'Read and write')]

    def __init__(self, fhir_version=FHIR_VERSION_4_0_1):
        self.fhir_version = fhir_version

        self.fhir_scopes = {**DEFAULT_SMART_SCOPES}
        self.fhir_scopes_by_resource_name = defaultdict(list)

        self._build_scope_messages()

    def _build_scope_messages(self):
        # Build all possible SMART-on-FHIR clinical and launch scopes
        # http://hl7.org/fhir/smart-app-launch/scopes-and-launch-context/index.html#clinical-scope-syntax
        # clinical-scope ::= ( 'patient' | 'user' ) '/' ( fhir-resource | '*' ) '.' ( 'read' | 'write' | '*' )
        for client_type, client_message in self.CLIENT_TYPES:
            for resource_name, description in self._get_fhir_resources() + [('*', 'all')]:
                for access_type, access_type_message in self.ACCESS_PERMISSIONS:
                    message = f"{access_type_message} {client_message} {resource_name} data: {description}"
                    scope = f"{client_type}/{resource_name}.{access_type}"

                    self.fhir_scopes[scope] = message
                    self.fhir_scopes_by_resource_name[resource_name].append(scope)

    def _get_fhir_resources(self):
        resources = []
        schema_dir = get_schema_dir(self.fhir_version)
        for filename in os.listdir(schema_dir):
            if filename == 'fhir.schema.json':
                continue
            with open(os.path.join(schema_dir, filename), 'r') as schema_file:
                json_schema_file = json.load(schema_file)
                resource_name = filename[:-(len('.schema.json'))]
                try:
                    description = json_schema_file['definitions'][resource_name]["allOf"][1]["description"]
                except (KeyError, IndexError):
                    description = ""
                resources.append((resource_name, description))
        return resources


class HQScopes(BaseScopes):
    scope_builder = FhirScopeBuilder()

    def get_all_scopes(self):
        # For clinical scopes, get all possible FHIR resources, and add any extra scopes we have defined
        return {**HQ_DEFINED_SCOPES, **self.scope_builder.fhir_scopes}

    def get_available_scopes(self, application=None, request=None, *args, **kwargs):
        # request param is an oauthlib.Request object, not a django request
        if application.hq_application.smart_on_fhir_compatible:
            domain = get_domain_from_url(request.uri)
            domain_resources = FHIRResourceType.objects.filter(domain=domain).distinct('name').values_list(
                'name', flat=True
            ).all()
            available_scopes = list(DEFAULT_SMART_SCOPES.keys())
            for resource in list(domain_resources) + ['*']:
                available_scopes += self.scope_builder.fhir_scopes_by_resource_name[resource]
            return available_scopes
        else:
            return HQ_DEFINED_SCOPES.keys()

    def get_default_scopes(self, application=None, requst=None, *args, **kwargs):
        return []
