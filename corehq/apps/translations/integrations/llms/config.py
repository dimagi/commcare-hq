import os

from django.conf import settings


class TranslationConfig:
    """Configuration for translation process."""

    DEFAULT_BATCH_SIZE = 50
    DEFAULT_ENVIRONMENT = 'dev'
    DEFAULT_RATE_LIMIT = 2  # seconds between API calls

    # Provider-specific defaults
    OPENAI_MODEL = 'gpt-4o-mini'

    # This is for local development
    LM_STUDIO_BASE_URL = "http://localhost:1234/v1"
    LM_STUDIO_MODEL = "mradermacher/Meta-Llama-3.1-8B-Instruct_CODE_Python_English_Asistant-16bit-v2-GGUF"

    def __init__(self, lang, **kwargs):
        self.language = lang

        self.batch_size = kwargs.get('batch_size', self.DEFAULT_BATCH_SIZE)
        self.environment = kwargs.get('env', self.DEFAULT_ENVIRONMENT)
        self.rate_limit = kwargs.get('rate_limit', self.DEFAULT_RATE_LIMIT)

        # Set provider-specific settings
        self.openai_api_key = kwargs.get('openai_api_key', getattr(settings, 'OPENAI_API_KEY', None))
        self.openai_model = kwargs.get('openai_model', self.OPENAI_MODEL)
        self.lm_studio_base_url = kwargs.get('lm_studio_base_url', self.LM_STUDIO_BASE_URL)
        self.lm_studio_model = kwargs.get('lm_studio_model', self.LM_STUDIO_MODEL)

    @property
    def is_production(self):
        return self.environment == 'prod'

    def get_locale_path(self):
        return os.path.join(settings.BASE_DIR, 'locale')

    def get_po_file_paths(self):
        locale_path = self.get_locale_path()
        po_file_path = os.path.join(locale_path, self.language, 'LC_MESSAGES', 'django.po')
        pojs_file_path = os.path.join(locale_path, self.language, 'LC_MESSAGES', 'djangojs.po')
        return [po_file_path, pojs_file_path]

    def get_provider_config(self):
        if self.is_production:
            return {
                'provider_type': 'openai',
                'api_key': self.openai_api_key,
                'model': self.openai_model
            }
        else:
            return {
                'provider_type': 'lm-studio',
                'base_url': self.lm_studio_base_url,
                'model': self.lm_studio_model
            }
