import json
import os
from abc import ABC

from django.conf import settings

from openai import OpenAI


class BaseTranslationProvider(ABC):
    """Base class with common functionality for translation providers."""

    def __init__(self, client, model):
        self.client = client
        self.model = model

    def get_batch_prompt(self, target_lang):
        return (
            f"Translate the following texts to {target_lang}. Keep the structure and formatting. "
            "Do not translate placeholders in curly braces, Python %-style strings, HTML tags, or URLs. "
            "Ensure translated text maintains leading/trailing newlines. "
            "Input: JSON array of objects with unique hash and message. "
            "Response: JSON object on the following format: "
            "{\"hash\":\"translated_message\", \"hash\":\"translated_message\", ...}"
            "Use double quotes and escape newlines."
        )

    def get_plural_batch_prompt(self, target_lang):
        return (
            f"Translate the following texts to {target_lang}. Keep the structure and formatting. "
            "Do not translate placeholders in curly braces, Python %-style strings, HTML tags, or URLs. "
            "Ensure translated text maintains leading/trailing newlines. "
            "Input: JSON array of objects with unique hash, singular, and plural messages. "
            "Response: JSON object on the following format: "
            "{\"hash\":{\"singular\":\"translated_singular\", \"plural\":\"translated_plural\"}, ...}"
            "Use double quotes and escape newlines."
        )


class OpenAITranslationProvider(BaseTranslationProvider):
    """Translation provider using OpenAI API."""

    def translate_batch(self, batch, target_lang):
        print(f"Translating batch of {len(batch)} strings")
        system_prompt = self.get_batch_prompt(target_lang)
        batch_str = json.dumps(batch)
        try:
            completion = self.make_request(system_prompt, batch_str)
            return json.loads(completion.choices[0].message.content)
        except Exception as e:
            # Fine to skip the batch if the LLM does not return a valid JSON
            # We will try to re-run the script again to get around with this issue.
            print(f"Error translating batch: {e}")
            print(completion.choices[0].message.content)
            return {}

    def make_request(self, system_prompt, batch_str):
        return self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": batch_str}
            ],
            temperature=0.2,
            response_format={
                "type": "json_object",
            },
        )

    def translate_plural_batch(self, batch, target_lang):
        print(f"Translating batch of {len(batch)} plural strings")
        system_prompt = self.get_plural_batch_prompt(target_lang)
        batch_str = json.dumps(batch)
        try:
            completion = self.make_request(system_prompt, batch_str)
            return json.loads(completion.choices[0].message.content)
        except Exception as e:
            print(f"Error translating plural batch: {e}")
            print(completion.choices[0].message.content)
            return {}


class LocalLMStudioProvider(BaseTranslationProvider):
    """Translation provider using local LM Studio."""

    # Implementation is identical to OpenAI for now since LM Studio uses the OpenAI API format
    def translate_batch(self, batch, target_lang):
        return OpenAITranslationProvider(self.client, self.model).translate_batch(batch, target_lang)

    def translate_plural_batch(self, batch, target_lang):
        return OpenAITranslationProvider(self.client, self.model).translate_plural_batch(batch, target_lang)


class TranslationProviderFactory:
    """Factory for creating translation providers."""

    @staticmethod
    def create_provider(provider_type, **kwargs):
        """
        Create a translation service based on the service type.

        Args:
            service_type: Type of service to create ('openai', 'lm-studio', etc.)
            **kwargs: Additional arguments for service configuration

        Returns:
            TranslationProvider: Configured translation provider
        """
        api_key = TranslationProviderFactory.get_api_key(provider_type)
        if provider_type == 'openai':
            if kwargs.get('api_key'):
                api_key = kwargs.get('api_key')
            client = OpenAI(api_key=api_key)
            model = kwargs.get('model', 'gpt-4o-mini')
            return OpenAITranslationProvider(client, model)
        elif provider_type == 'lm-studio':
            client = OpenAI(
                api_key=api_key,
                base_url=kwargs.get('base_url', "http://localhost:1234/v1")
            )
            model = kwargs.get('model')
            return LocalLMStudioProvider(client, model)
        else:
            raise ValueError(f"Unknown provider type: {provider_type}")

    @staticmethod
    def get_api_key(provider_type):
        if provider_type == 'openai':
            return os.environ.get('OPENAI_API_KEY') or settings.OPENAI_API_KEY
        elif provider_type == 'lm-studio':
            return 'lm-studio'
        else:
            raise ValueError(f"Unknown provider type: {provider_type}")
