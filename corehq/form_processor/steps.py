import re
from abc import ABC, abstractmethod

from corehq.apps.data_vault.models import VaultStore


class FormProcessingStep(ABC):
    @abstractmethod
    def __call__(self, *args, **kwargs):
        """
        Process the form context object. Return an instance of
        FormProcessingResult to terminate the processing or None
        To allow processing to continue to the next step
        """
        pass


class VaultPatternExtractor(FormProcessingStep):
    identifier = None

    def __init__(self, patterns, xmlns_whitelist=None):
        self._patterns = patterns
        self._xmlns_whitelist = xmlns_whitelist

    def __call__(self, context):
        if self._should_process(context.instance_xml):
            return self._process(context)

    def _should_process(self, xml_as_text):
        for xmlns in self._xmlns_whitelist:
            if xmlns in xml_as_text:
                return True
        return False

    def _process(self, context):
        new_xml, vault_items = self._replace_values(context.instance_xml)
        context.instance_xml = new_xml
        context.supplementary_models.append(vault_items)

    def _replace_values(self, xml_as_text):
        values = self._extract_patterns_from_string(xml_as_text, self._patterns)
        distinct_values = set(values)
        vault_items = [VaultStore(value=value, identifier=self.identifier) for value in distinct_values]
        new_xml = self._replace_keys_in_string({v.value: v.key for v in vault_items}, xml_as_text)
        return new_xml, vault_items

    @staticmethod
    def _extract_patterns_from_string(text, patterns):
        values = []
        for pattern in patterns:
            result = re.match(pattern, text)
            if re.match(pattern, text):
                values.append(list(result.groups()))
        return values

    @staticmethod
    def _replace_keys_in_string(replacements, text, prefix='vault:'):
        for old_text, new_text in replacements.items():
            text = text.replace(old_text, prefix + new_text)
        return text
