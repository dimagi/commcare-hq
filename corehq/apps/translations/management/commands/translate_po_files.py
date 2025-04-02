import abc
import json
import os
import re
from functools import cached_property

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

import gevent
import polib
import requests
from memoized import memoized


@memoized
def langcode_to_langname_map():
    langs = settings.LANGUAGES
    lang_name_map = {}
    for lang_code, lang_name in langs:
        lang_name_map[lang_code] = lang_name
    return lang_name_map


class LLMTranslator(abc.ABC):
    """
    Abstract class for different LLM translators. This class can be extended to support different LLM clients.
    In this case, we will be implementing a class for OpenAI.
    """

    def __init__(self, api_key, model, lang, translation_format):
        """
        :param api_key: str
        :param model: str
        :param translation_format: an instance of TranslationFormat or its subclass
        """
        self.api_key = api_key
        assert model in self.supported_models, f"Model {model} is not supported by {self.__class__.__name__}."
        self.model = model
        self.lang = lang
        self.translation_format = translation_format

    def base_prompt(self):
        lang_map = langcode_to_langname_map()
        lang_name = lang_map.get(self.lang, self.lang)
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
        """Call LLM using the client library"""
        pass

    @abc.abstractmethod
    def _call_llm_http(self, system_prompt, user_message):
        """Call LLM using direct HTTP requests without client libraries"""
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
    def load_input(self, file_path=None):
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
        return ["gpt-4o-mini", "gpt-4o", "gpt-4", "gpt-3.5-turbo"]

    def __init__(self, api_key, model, lang, translation_format):
        super().__init__(api_key, model, lang, translation_format)
        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=api_key)
        except ImportError:
            self.client = None
            print("OpenAI Python package not found, will use HTTP requests instead.")

        self.api_base = "https://api.openai.com/v1"

    def _call_llm(self, system_prompt, user_message):
        if self.client is None:
            return self._call_llm_http(system_prompt, user_message)
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"Error calling OpenAI API via client: {e}")
            raise e

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
            print(f"Error making HTTP request to OpenAI API: {e}")
            raise e


class PoTranslationFormat(TranslationFormat):

    def __init__(self, file_path):
        self.file_path = file_path
        self.translation_obj_map = {}

    def load_input(self, po_objects=[]):
        """
        :param po_objects: a list of polib.Message objects, if not provided,
        we will use the untranslated messages from the PO file.
        :return: a list of polib.Message objects
        """
        po_objects = self.untranslated_messages if po_objects == [] else po_objects
        self.translation_obj_map = self._build_translation_obj_map(po_objects)
        return po_objects

    @cached_property
    def all_message_objects(self):
        try:
            return polib.pofile(self.file_path)
        except FileNotFoundError:
            """If the file is not found, we will return an empty list."""
            raise FileNotFoundError(f"File {self.file_path} not found.")

    @property
    def untranslated_messages(self):
        return [msg for msg in self.all_message_objects if msg.msgstr == ""]

    @property
    def untranslated_messages_plural(self):
        return [msg for msg in self.all_message_objects if msg.msgid_plural != "" and msg.msgstr_plural[0] == ""]

    def _build_translation_obj_map(self, translations):
        """
        Build a map of message objects to their index.
        This is used to format the input for the LLM.
        :param translations: a list of polib.Message objects
        :return: a dict of message objects to their index
        """
        translation_obj_map = {}
        for index, message_obj in enumerate(translations):
            translation_obj_map[str(index)] = message_obj
        return translation_obj_map

    def format_input(self, msg_id_batch):
        batch_dict = {}
        for index, message_obj in msg_id_batch.items():
            batch_dict[index] = message_obj.msgid
        return json.dumps(batch_dict)

    def create_batches(self, input_data=[], batch_size=10):
        """
        :param input_data: a list of objects with mapping of increasing number and message of the following format:
        {
            "0": "msgid",
            "1": "msgid",
            ...
        }
        which is basically output of `build_translation_obj_map`
        :param batch_size: the number of objects per batch
        :return: an array of batches, each batch is a dict of increasing number and message
        """
        self.load_input(input_data)
        input_data_list = list(self.translation_obj_map.items())
        return [dict(input_data_list[i:i + batch_size]) for i in range(0, len(input_data_list), batch_size)]

    def parse_output(self, output_data):
        try:
            llm_output = json.loads(output_data)
            filtered_output = {
                msg_id: msg_str
                for msg_id, msg_str in llm_output.items()
                if self.is_valid_msgstr(self.translation_obj_map[msg_id].msgid, msg_str)
            }
            self.fill_translations(filtered_output)
            return filtered_output
        except json.JSONDecodeError:
            """There have been cases when the output returned by llm is not a valid json object.
            In that case, we will return an empty dict.
            And it is safe to do it because the untranslated messages will
            be translated in the next run of the script.
            """
            return {}

    @staticmethod
    def is_valid_msgstr(msgid, msgstr):
        """
        Tests if a given msgstr is likely to cause issues during compilemessages or runtime.
        It was observed that the LLM sometimes returns msgstrs that are not valid.
        This function is used to filter out those invalid msgstrs.
        Its a longish function that checks for various issues with the msgstr, each step is
        defined in the comment above the code.
        Regexes are generated using LLMs to check for invalid msgstrs but iterated over
        multiple times to be more robust and have related tests to check for false positives.

        Args:
            msgid (str): The original msgid.
            msgstr (str): The translated msgstr.

        Returns:
            bool: True if msgstr is likely valid, False otherwise.
        """

        def print_error(msg):
            _msgid = msgid[:200] + '...' if len(msgid) > 200 else msgid
            _msgstr = msgstr[:200] + '...' if len(msgstr) > 200 else msgstr
            print(f"Validation Error: {msg}")
            print(f"  msgid: {_msgid}")
            print(f"  msgstr: {_msgstr}")

        # 1. Placeholders
        # Finds %-style (like %s, %(name)s), {}-style
        placeholder_pattern = r'%(?:\([^)]+\))?[a-zA-Z%]|{.*?}'
        msgid_placeholders = re.findall(placeholder_pattern, msgid)
        msgstr_placeholders = re.findall(placeholder_pattern, msgstr)

        if set(msgid_placeholders) != set(msgstr_placeholders):
            print_error(
                f"Placeholder mismatch. msgid: {msgid_placeholders}, "
                f"msgstr: {msgstr_placeholders}")
            return False

        # 2. HTML Tags (Important for structure)
        # Extracts tags like <tag>, </tag>, <tag/>
        html_tag_pattern = r'<[/!]?\w+(?:\s+[^>]*)?/?>'  # More robust tag matching
        msgid_tags = re.findall(html_tag_pattern, msgid)
        msgstr_tags = re.findall(html_tag_pattern, msgstr)

        if len(msgid_tags) != len(msgstr_tags):
            print_error(f"HTML tag count mismatch. msgid: {len(msgid_tags)}, msgstr: {len(msgstr_tags)}")
            return False
        elif msgid_tags:
            # Compare tag names and types (opening/closing) in sequence
            # This allows for changes in attributes, which is often acceptable
            msgid_tag_info = [re.match(r'<(/?)(\w+)', tag).groups()
                              for tag in msgid_tags if re.match(r'<(/?)(\w+)', tag)]
            msgstr_tag_info = [re.match(r'<(/?)(\w+)', tag).groups()
                               for tag in msgstr_tags if re.match(r'<(/?)(\w+)', tag)]
            if msgid_tag_info != msgstr_tag_info:
                print_error(
                    f"HTML tag sequence or type mismatch. msgid tags: {msgid_tag_info}, "
                    f"msgstr tags: {msgstr_tag_info}")
                return False

        # 3. URLs
        # First find all URLs, then strip trailing periods for comparison
        url_pattern = r'https?://[^\s<>"]+|www\.[^\s<>"]+'
        msgid_urls = re.findall(url_pattern, msgid)
        if msgid_urls:
            msgstr_urls = re.findall(url_pattern, msgstr)
            chars_to_strip = '.\\'
            msgid_urls = [url.rstrip(chars_to_strip) for url in msgid_urls]
            msgstr_urls = [url.rstrip(chars_to_strip) for url in msgstr_urls]

            if set(msgid_urls) != set(msgstr_urls):
                print_error(f"URLs mismatch. msgid: {msgid_urls}, msgstr: {msgstr_urls}")
                return False

        # 4. Encoding
        try:
            msgstr.encode('utf-8')
        except UnicodeEncodeError as e:
            print_error(f"Invalid UTF-8 encoding: {e}")
            return False
        return True

    def fill_translations(self, llm_output):
        for index, msg_str in llm_output.items():
            self.translation_obj_map[index].msgstr = msg_str

    def save_output(self):
        """
        Save the translations to the PO file.
        """
        self.all_message_objects.save()

    def format_input_description(self):
        return "- Ensure that translations are gender neutral unless the original text is gender specific. " \
               "- Do not translate placeholders in curly braces, Python %-style strings, HTML tags, or URLs. " \
               "- Ensure translated text maintains leading/trailing newlines. " \
               "- Every translated message should be valid `msgstr` and should adhere to all of its specs." \
               "- Special characters like double quotes (\") and backslashes (\\) must be escaped"\
               "a with backslash." \
               "Input: JSON array of objects with unique hash and message of the following format: " \
               "{\"0\":\"msgid\", \"1\":\"msgid\", ...}"

    def format_output_description(self):
        return "Response: JSON object on the following format: " \
               "{\"0\":\"translated_message for key 0\", \"1\":\"translated_message for key 1\", ...}"


class Command(BaseCommand):
    help = 'Translate PO files using LLM models'

    def add_arguments(self, parser):
        parser.add_argument(
            '--model',
            type=str,
            required=True,
            help='LLM model to use for translation (e.g., gpt-4o-mini, gpt-4o, gpt-4, gpt-3.5-turbo)'
        )
        parser.add_argument(
            '--langs',
            type=str,
            nargs='+',
            help='Language codes to translate to. If not provided, uses all languages from settings.LANGUAGES'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=30,
            help='Number of messages to translate in each batch (default: 30)'
        )
        parser.add_argument(
            '--api-key',
            type=str,
            help='API key for the LLM service. If not provided, will check settings.OPENAI_API_KEY or '
                 'OPENAI_API_KEY env var'
        )
        parser.add_argument(
            '--parallel-batches',
            type=int,
            default=10,
            help='Number of batches to process in parallel (default: 10)'
        )

    def handle(self, *args, **options):
        model = options['model']
        langs = options['langs'] or [lang[0] for lang in settings.LANGUAGES]
        batch_size = options['batch_size']
        parallel_batches = options['parallel_batches']

        api_key = options['api_key']
        if not api_key:
            api_key = getattr(settings, 'OPENAI_API_KEY', None)
        if not api_key:
            api_key = os.environ.get('OPENAI_API_KEY')
        if not api_key:
            raise CommandError(
                "API key not found. Please provide it via:\n"
                "1. --api-key command line argument\n"
                "2. settings.OPENAI_API_KEY in Django settings\n"
                "3. OPENAI_API_KEY environment variable"
            )

        self.stdout.write(f"Starting translation with model {model} for languages: {', '.join(langs)}")
        self.stdout.write(f"Batch size: {batch_size}, Parallel batches: {parallel_batches}")

        for lang in langs:
            po_file_paths = [
                f"locale/{lang}/LC_MESSAGES/django.po",
                f"locale/{lang}/LC_MESSAGES/djangojs.po"
            ]
            self.stdout.write(f"\nProcessing language: {lang}")
            for po_file_path in po_file_paths:
                try:
                    if not os.path.exists(po_file_path):
                        self.stderr.write(f"PO file not found: {po_file_path}")
                        continue
                    self.stdout.write(f"Processing PO file: {po_file_path}")
                    self._translate_language(lang, model, api_key, batch_size, parallel_batches, po_file_path)
                except Exception as e:
                    self.stderr.write(f"Error processing language {lang}: {str(e)}")

    def _translate_language(self, lang, model, api_key, batch_size, parallel_batches, po_file_path):
        translation_format = PoTranslationFormat(po_file_path)
        translator = OpenaiTranslator(
            api_key=api_key,
            model=model,
            lang=lang,
            translation_format=translation_format
        )

        untranslated = translation_format.load_input()
        if not untranslated:
            self.stdout.write(f"No untranslated messages found for {lang}")
            return

        batches = translation_format.create_batches(untranslated, batch_size=batch_size)
        self.stdout.write(f"Found {len(untranslated)} untranslated messages in {len(batches)} batches")

        pool = gevent.pool.Pool(parallel_batches)
        completed_batches = 0
        total_batches = len(batches)

        def process_batch(batch_data, batch_index):
            try:
                translation = translator.translate(batch_data)
                if translation:
                    self.stdout.write(f"Successfully translated batch {batch_index + 1}/{total_batches}")
                    translation_format.save_output()
                    return translation
                else:
                    self.stderr.write(f"No valid translations received for batch {batch_index + 1}")
                    return {}
            except Exception as e:
                self.stderr.write(f"Error processing batch {batch_index + 1}: {str(e)}")
                return {}

        jobs = []
        for i, batch in enumerate(batches):
            job = pool.spawn(process_batch, batch, i)
            jobs.append(job)

        for job in jobs:
            try:
                result = job.get()
                if result:
                    completed_batches += 1
            except Exception as e:
                self.stderr.write(f"Error in batch processing: {str(e)}")

        translation_format.save_output()
        self.stdout.write(
            f"Completed translation for {lang}. "
            f"Successfully processed {completed_batches}/{total_batches} batches."
        )
