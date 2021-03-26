import json
import os

from oauth2_provider.scopes import BaseScopes

from corehq.motech.fhir.const import FHIR_VERSION_4_0_1
from corehq.motech.fhir.models import get_schema_dir


def _smart_on_fhir_scopes(version=FHIR_VERSION_4_0_1):
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

    fhir_scopes = {
        'launch/patient': 'Access your unique patient ID',
        'offline_access': 'Maintain access to your data',
        'online_access': 'Maintain access to your data',
    }
    for client_type, client_message in [('patient', 'your patients\''), ('user', 'your')]:
        for resource_name, description in resources + [('*', 'all')]:
            for access_type, access_type_message in [('read', 'Read'), ('write', 'Write'),
                                                     ('*', 'Read and write')]:
                message = f"{access_type_message} {client_message} {resource_name} data: {description}"
                fhir_scopes[f"{client_type}/{resource_name}.{access_type}"] = message

    return fhir_scopes


SMART_ON_FHIR_SCOPES = _smart_on_fhir_scopes()
HQ_DEFINED_SCOPES = {
    'access_apis': 'Access API data on all your CommCare projects',
}


class HQScopes(BaseScopes):

    def get_all_scopes(self):
        # For clinical scopes, get all possible FHIR resources, and add any extra scopes we have defined

        return {**HQ_DEFINED_SCOPES, **SMART_ON_FHIR_SCOPES}

    def get_available_scopes(self, application=None, request=None, *args, **kwargs):
        # TODO:
        # From the domain, get the scopes available from the Data Dictionary
        # Differentiate between SMART applications, and other OAuth applications.

        return self.get_all_scopes().keys()

    def get_default_scopes(self, application=None, requst=None, *args, **kwargs):
        return self.get_all_scopes().keys()
