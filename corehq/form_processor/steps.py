import re
from abc import ABC, abstractmethod

from corehq.apps.data_vault import new_vault_entry


class FormProcessingStep(ABC):
    @abstractmethod
    def __call__(self, context):
        """
        Process the form context object. Return an instance of
        FormProcessingResult to terminate the processing or None
        To allow processing to continue to the next step
        :param context: form context
        """
        pass


class VaultPatternExtractor(FormProcessingStep):
    def __init__(self, patterns, xmlns_whitelist=None):
        self._patterns = patterns
        self._xmlns_whitelist = xmlns_whitelist or []

    def __call__(self, context):
        if self._should_process(context.instance_xml):
            return self._process(context)

    def _should_process(self, xml_as_text):
        if not self._xmlns_whitelist:
            return True
        for xmlns in self._xmlns_whitelist:
            if xmlns in xml_as_text:
                return True
        return False

    def _process(self, context):
        new_xml, vault_items = self._replace_values(context.instance_xml)
        context.instance_xml = new_xml
        context.supplementary_models.extend(vault_items)

    def _replace_values(self, xml_as_text):
        values = self._extract_patterns_from_string(xml_as_text, self._patterns)
        distinct_values = set(values)
        vault_items = [new_vault_entry(value=value) for value in distinct_values]
        new_xml = self._replace_keys_in_string({v.value: v.key for v in vault_items}, xml_as_text)
        return new_xml, vault_items

    @staticmethod
    def _extract_patterns_from_string(text, patterns):
        values = []
        for pattern in patterns:
            values.extend(re.findall(pattern, text))
        return values

    @staticmethod
    def _replace_keys_in_string(replacements, text, prefix='vault:'):
        for old_text, new_text in replacements.items():
            text = text.replace(old_text, prefix + new_text)
        return text
