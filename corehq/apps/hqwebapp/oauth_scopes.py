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


def _all_clinical_scopes(version=FHIR_VERSION_4_0_1):
    # Build all possible SMART-on-FHIR clinical and launch scopes
    # http://hl7.org/fhir/smart-app-launch/scopes-and-launch-context/index.html#clinical-scope-syntax
    # clinical-scope ::= ( 'patient' | 'user' ) '/' ( fhir-resource | '*' ) '.' ( 'read' | 'write' | '*' )

    resources = []
    schema_dir = get_schema_dir(version)
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

    fhir_scopes = {**DEFAULT_SMART_SCOPES}
    fhir_scopes_by_resource_name = defaultdict(list)
    for client_type, client_message in [('patient', 'your patients\''), ('user', 'your')]:
        for resource_name, description in resources + [('*', 'all')]:
            for access_type, access_type_message in [('read', 'Read'), ('write', 'Write'),
                                                     ('*', 'Read and write')]:
                message = f"{access_type_message} {client_message} {resource_name} data: {description}"
                scope = f"{client_type}/{resource_name}.{access_type}"
                fhir_scopes[scope] = message
                fhir_scopes_by_resource_name[resource_name].append(scope)

    return fhir_scopes, fhir_scopes_by_resource_name


ALL_CLINICAL_SCOPES, CLINICAL_SCOPES_BY_RESOURCE_NAME = _all_clinical_scopes()


class HQScopes(BaseScopes):

    def get_all_scopes(self):
        # For clinical scopes, get all possible FHIR resources, and add any extra scopes we have defined

        return {**HQ_DEFINED_SCOPES, **ALL_CLINICAL_SCOPES}

    def get_available_scopes(self, application=None, request=None, *args, **kwargs):
        # request param is an oauthlib.Request object, not a django request
        if application.smart_on_fhir_compatible:
            domain = get_domain_from_url(request.uri)
            resources = FHIRResourceType.objects.filter(domain=domain).distinct('name').values_list(
                'name', flat=True
            ).all()
            available_scopes = list(DEFAULT_SMART_SCOPES.keys())
            for resource in resources:
                available_scopes += CLINICAL_SCOPES_BY_RESOURCE_NAME[resource]
            return available_scopes

        return HQ_DEFINED_SCOPES.keys()

    def get_default_scopes(self, application=None, requst=None, *args, **kwargs):
        return []
