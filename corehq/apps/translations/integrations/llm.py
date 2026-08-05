"""LLM-backed translation: provider clients and the TranslationFormat seam.

Shared by the PO-file translation management command and AI app
translations. Formats adapt a content source to the flat JSON batch
protocol ({"0": "text", ...} in, {"0": "translation", ...} out);
providers are interchangeable behind ``LLMTranslator``.
"""
import abc
import random

import gevent
import requests

from langcodes import get_name as _langcodes_get_name


def language_name(lang_code):
    """Human-readable name for an HQ app language code (2- or 3-letter)."""
    return _langcodes_get_name(lang_code) or lang_code


def retry_with_exponential_backoff(
    initial_delay=1, exponential_base=2, jitter=True,
    max_retries=10, errors=(Exception,), backup_model=''
):
    """
    :param initial_delay: initial delay in seconds
    :param exponential_base: exponential base for the delay
    :param jitter: whether to add randomness to the delay
    :param max_retries: maximum number of retries
    :param errors: tuple of errors to catch
    :param backup_model: when the primary model is rate limited,
        this model will be used,optional, default is ''

    This approach has been inspired by the approaches suggested in
    https://github.com/openai/openai-cookbook/blob/main/examples/How_to_handle_rate_limits.ipynb
    We are adding exponential backoff on retries and also a backup model to use
    if the primary model is rate limited.

    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            num_retries = 0
            delay = initial_delay

            while True:
                try:
                    return func(*args, **kwargs)
                except errors:
                    num_retries += 1
                    if num_retries == 1 and backup_model:
                        print(f"Rate limit error, retrying with backup model: {backup_model}")
                        return func(*args, **kwargs, backup_model=backup_model)
                    if num_retries > max_retries:
                        raise Exception(
                            f"Maximum number of retries ({max_retries}) exceeded."
                        )
                    delay *= exponential_base * (1 + jitter * random.random())
                    gevent.sleep(delay)
                except Exception as e:
                    raise Exception("Error calling LLM") from e
        return wrapper
    return decorator


class LLMTranslator(abc.ABC):
    """
    Abstract class for different LLM translators. This class can be extended to support different LLM clients.
    In this case, we will be implementing a class for OpenAI.
    """

    def __init__(self, api_key, model, lang, translation_format, backup_model=''):
        """
        :param api_key: str
        :param model: str
        :param translation_format: an instance of TranslationFormat or its subclass
        :param backup_model: when the primary model is rate limited,
            this model will be used, optional, default is ''
        """
        self.api_key = api_key
        assert model in self.supported_models, f"Model {model} is not supported by {self.__class__.__name__}."
        self.model = model
        self.lang = lang
        self.backup_model = backup_model
        self.translation_format = translation_format

    def base_prompt(self):
        lang_name = language_name(self.lang)
        base_prompt = f"""You are a professional translator. Translate the following texts to {lang_name}.
        Keep the structure and formatting of the original text."""
        return base_prompt

    def input_format_prompt(self):
        return f"Input format: {self.translation_format.format_input_description()}"

    def output_format_prompt(self):
        return f"Output format: {self.translation_format.format_output_description()}"

    @abc.abstractmethod
    def supported_models(self):
        return []

    def translate(self, input_data):
        system_prompt = "\n".join([
            self.base_prompt(),
            self.input_format_prompt(),
            self.output_format_prompt(),
        ])
        user_message = self.translation_format.format_input(input_data)

        llm_output = self._call_llm(system_prompt, user_message)
        return self.translation_format.parse_output(llm_output)

    @abc.abstractmethod
    def _call_llm(self, system_prompt, user_message):
        pass

    @abc.abstractmethod
    def _call_llm_http(self, system_prompt, user_message):
        pass


class TranslationFormat(abc.ABC):
    """
    Abstract class for different translation formats.
    The idea is to have a class for each format and have input prompt and output prompt for each format.
    Defined in the subclasses. It also has methods to load input, format input, parse output, save output.
    An example can be we can have a class for Simple text file, JSON file etc.
    We have implemented a class for PO file translation.
    """
    @abc.abstractmethod
    def load_input(self, input_source=None):
        pass

    @abc.abstractmethod
    def format_input(self, input_data):
        pass

    @abc.abstractmethod
    def parse_output(self, output_data):
        pass

    @abc.abstractmethod
    def save_output(self, output_data, output_path):
        pass

    @abc.abstractmethod
    def format_input_description(self):
        pass

    @abc.abstractmethod
    def format_output_description(self):
        pass


class OpenaiTranslator(LLMTranslator):
    @property
    def supported_models(self):
        return ["gpt-4o-mini", "gpt-4o", "gpt-4", "gpt-4.1"]

    def __init__(self, api_key, model, lang, translation_format, backup_model=''):
        super().__init__(api_key, model, lang, translation_format, backup_model=backup_model)
        try:
            import openai
            self.openai = openai
            self.client = openai.OpenAI(api_key=api_key)
        except ImportError:
            self.openai = None
            self.client = None
            print("OpenAI Python package not found, will use HTTP requests instead.")

        self.api_base = "https://api.openai.com/v1"

    def _call_llm(self, system_prompt, user_message):

        if self.client is None:
            return self._call_llm_http(system_prompt, user_message)

        @retry_with_exponential_backoff(
            max_retries=5, errors=(self.openai.RateLimitError,), backup_model=self.backup_model
        )
        def _call_openai_client(backup_model=None):
            model = backup_model or self.model
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            return response.choices[0].message.content

        try:
            return _call_openai_client()
        except Exception as e:
            raise Exception("OpenAI API call failed") from e

    def _call_llm_http(self, system_prompt, user_message):
        # We might not use this method at all, but it was useful in testing other LLM clients
        # without installing their package, so I am keeping it here for now.
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                "temperature": 0.2,
                "response_format": {"type": "json_object"}
            }

            response = requests.post(
                f"{self.api_base}/chat/completions",
                headers=headers,
                json=payload
            )
            response.raise_for_status()

            result = response.json()
            return result["choices"][0]["message"]["content"]
        except Exception as e:
            raise Exception("Error making HTTP request to OpenAI API") from e
