from corehq.form_processor.steps import VaultPatternExtractor


class TestVaultPatternExtractor(VaultPatternExtractor):
    def __init__(self):
        super(TestVaultPatternExtractor, self).__init__(
            patterns=[r'<secret_case_property>(\d{10})<\/secret_case_property>'],
        )
