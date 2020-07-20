from corehq.form_processor.steps import VaultPatternExtractor


AADHAAR_XFORM_SUBMISSION_PATTERNS = [r'<aadhar_number>(\d{12})<\/aadhar_number>']
AADHAAR_FORMS_XMLNSES = []


class AadhaarNumberExtractor(VaultPatternExtractor):
    identifier = "AadhaarNumber"

    def __init__(self):
        super(AadhaarNumberExtractor, self).__init__(
            patterns=AADHAAR_XFORM_SUBMISSION_PATTERNS,
            xmlns_whitelist=AADHAAR_FORMS_XMLNSES
        )
