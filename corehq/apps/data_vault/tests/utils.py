from corehq.form_processor.steps import VaultPatternExtractor


class DummyVaultPatternExtractor(VaultPatternExtractor):
    def __init__(self):
        super(DummyVaultPatternExtractor, self).__init__(
            patterns=[r'<secret_case_property>(\d{10})<\/secret_case_property>'],
        )
