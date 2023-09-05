# Input is FHIR data in JSON for a HI Type
# Output is what needs to be displayed on the UI

# Based on what needs to be displayed for the HI Type, create a JSON Response
# Option 1: Load the data into Python Models (fhir_client) and create response body by accessing model properties
# Option 2: Directly read JSON object for fields to be displayed.

import json
SAMPLE_FHIR_BUNDLE = '/home/ajeet/ldrive/dev/Resources/abdm/sample fhir records/pathology_sample.json'
with open(SAMPLE_FHIR_BUNDLE) as user_file:
    parsed_json = json.load(user_file)

# Using Option 1
from fhirclient.models.bundle import Bundle, BundleEntry
data = Bundle(jsondict=parsed_json)


# TODO Create Response body format
# Each Health Info Request can have
#   - multiple care contexts
#   - can have multiple HI types
# Each Care Context may have multiple entries associated (Depends on the project)
