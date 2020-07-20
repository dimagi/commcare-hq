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
        pass
