

def fhir_data_care_context(care_context_id):
    # To be implemented on HQ side
    # TODO FIGURE out how to do this For package purpose, this will raise NotImplememtedError
    # TODO Load Real data
    import json
    SAMPLE_FHIR_BUNDLE = '/home/ajeet/ldrive/dev/Resources/abdm/sample fhir records/pathology_sample.json'
    with open(SAMPLE_FHIR_BUNDLE) as user_file:
        parsed_json = json.load(user_file)
    return parsed_json
