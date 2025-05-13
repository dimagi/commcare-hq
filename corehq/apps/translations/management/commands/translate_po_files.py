import abc
import json
import os
import random
import re
import subprocess
import sys
from functools import cached_property

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

import gevent
import polib
import requests
from memoized import memoized


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
        super().__init__(api_key, model, lang, translation_format)
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


class PoTranslationFormat(TranslationFormat):
    """
    Translation format for PO files. The class expects gettext installed in the system.
    As it uses gettext's msgfmt command to check for errors in the PO file.
    """

    def __init__(self, file_path):
        self.file_path = file_path
        self.translation_obj_map = {}

    def load_input(self, input_source=None):
        """
        :param input_source: a list of polib.Message objects, if not provided,
        we will use the untranslated messages from the PO file.
        :return: a list of polib.Message objects
        """
        if not input_source:
            input_source = self.untranslated_messages
        self.translation_obj_map = self._build_translation_obj_map(input_source)
        return input_source

    @cached_property
    def all_message_objects(self):
        try:
            return polib.pofile(self.file_path)
        except FileNotFoundError:
            """If the file is not found, we will return an empty list."""
            raise FileNotFoundError(f"File {self.file_path} not found.") from None

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

    def create_batches(self, input_data=None, batch_size=10):
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
        if not input_data:
            input_data = []
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

    def check_and_remove_errored_messages(self, lang_path):
        """
        Checks PO files using gettext's msgfmt and removes translations that are problematic.
        These problematic translations are those that cause errors during compilemessages or runtime.
        """
        error_output = self._run_msgfmt(lang_path)
        if not error_output:
            print(f"No errors found in the PO file - {lang_path}")
            return
        line_num_error_map = self._extract_errored_msgstr_ids(error_output)
        if line_num_error_map:
            self._remove_errored_translations(line_num_error_map)

    def _run_msgfmt(self, lang_path):
        """
        Runs the gettext `msgfmt` command and returns any erroring msgstrs.
        Returns:
            str: The error output from the compilemessages command
        """
        try:
            args = ['msgfmt', '--check', '-o', '/dev/null', lang_path]
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                check=False
            )
            return result.stderr
        except Exception as e:
            print(f"Error running compilemessages: {e}")
            return ""

    def _extract_errored_msgstr_ids(self, error_output):
        line_num_error_map = {}

        for line in error_output.splitlines():
            # Error format: <filename>:<line_number>:<error_message>
            # Warning format: <filename>:<line_number>: warning<warning_message>
            error_parts = line.split(':')
            if len(error_parts) == 3 or len(error_parts) == 4:
                if error_parts[2].strip() == 'warning':
                    # Ignore warnings
                    continue
                line_num = int(error_parts[1].strip())
                line_num_error_map[line_num] = ": ".join(error_parts[2:]).strip()
        print(f"Line num error map: {line_num_error_map}")
        return line_num_error_map

    def _remove_errored_translations(self, line_num_error_map):
        """
        Removes translations for the specified message IDs.
        Since we have line numbers of msgstrs that are causing errors. In `polib`
        there is no way to get the msgid for a given line number.
        So this function uses following approach:

            1. Load the PO file again and sort the message objects by linenum.
            2. Iterate over the sorted message objects and check if the errored line number
            is in between the current and next msgid.
            3. If it is, remove the translation and get the next errored line number.
            4. If we run out of errored line numbers, break the loop.
            5. Save the PO file.

        Args:
            line_num_error_map (dict): A dict of line numbers and error messages
        """
        count = 0
        errored_msgstr_line_nums = sorted(line_num_error_map.keys())
        msg_str_lin_num = errored_msgstr_line_nums.pop(0)

        total_translations = len(self.all_message_objects)
        # After the translations file is saved, the linenumbers are changed.
        # So we need to load the file again and sort the message objects by linenum.
        all_translations = polib.pofile(self.file_path)
        sorted_message_objects = sorted(all_translations, key=lambda x: x.linenum)

        for index, entry in enumerate(sorted_message_objects):
            try:
                current_msgid_line_num = entry.linenum
                if index == total_translations - 1:
                    next_msgid_line_num = sys.maxsize
                else:
                    next_msgid_line_num = sorted_message_objects[index + 1].linenum
                if current_msgid_line_num < msg_str_lin_num < next_msgid_line_num:
                    print("--------------------------------")
                    print("Removing translation")
                    print(f"Error: {line_num_error_map[msg_str_lin_num]}")
                    print(f"msgid: {entry.msgid} at line {current_msgid_line_num}")
                    print(f"msgstr: {entry.msgstr}")
                    print("--------------------------------")
                    entry.msgstr = ""
                    count += 1
                    if len(errored_msgstr_line_nums) > 0:
                        msg_str_lin_num = errored_msgstr_line_nums.pop(0)
                    else:
                        break
            except Exception as e:
                print(f"Error removing translation for {entry.msgid} at line {current_msgid_line_num}: {e}")

        print("Remaining Problematic Translations", errored_msgstr_line_nums)

        if count > 0:
            print(f"Removed {count} problematic translations")
            all_translations.save()


class Command(BaseCommand):
    help = 'Translate PO files using LLM models'

    def add_arguments(self, parser):
        parser.add_argument(
            '--model',
            type=str,
            default='gpt-4.1',
            help='LLM model to use for translation (e.g., gpt-4o-mini, gpt-4o, gpt-4.1)'
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
            default=50,
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
            default=15,
            help='Number of batches to process in parallel (default: 10)'
        )
        parser.add_argument(
            '--check-and-remove-errors',
            action='store_true',
            help='If this flag is provided, the script will only check for errors in the existing '
                 'translations and remove them. It will not translate any new messages.'
        )

    def handle(self, *args, **options):
        self.check_and_remove_errors = options['check_and_remove_errors']
        model = options['model']
        langs = options['langs'] or [lang[0] for lang in settings.LANGUAGES if lang[0] != 'en']
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
            translation_format=translation_format,
            backup_model='gpt-4o'  # Hard coded right now, but can be made dynamic if needed
        )
        untranslated = translation_format.load_input()
        if self.check_and_remove_errors:
            translation_format.check_and_remove_errored_messages(po_file_path)
            return
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
        translation_format.check_and_remove_errored_messages(po_file_path)
        self.stdout.write(
            f"Completed translation for {lang}. "
            f"Successfully processed {completed_batches}/{total_batches} batches."
        )
