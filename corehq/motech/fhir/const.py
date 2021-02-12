FHIR_VERSION_4_0_1 = '4.0.1'
FHIR_VERSIONS = [
    (FHIR_VERSION_4_0_1, 'R4'),
]

# The XMLNS to use for forms for data imported from a remote FHIR
# service. e.g. Setting `external_id` on a case to its FHIR ID, or cases
# created or updated in CommCare via our FHIR API. This is to prevent
# FHIRRepeater from sending data from a FHIR service back again.
XMLNS_FHIR = 'http://commcarehq.org/fhir-engine-read'
