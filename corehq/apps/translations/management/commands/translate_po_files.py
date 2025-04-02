import abc
import json
import re
from functools import cached_property

from django.conf import settings

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
                if self._is_valid_msgstr(msg_id, msg_str)
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
    def _is_valid_msgstr(msgid, msgstr):
        """
        Tests if a given msgstr is valid according to PO file specifications.
        This is required because the LLM sometimes returns invalid msgstrs which messes up the po files.
        And these files fail in the compile step.
        This function is generated by LLMs but have been modified to be more robust.
        :param msgid: the original msgid
        :param msgstr: the translated msgstr
        :return: True if msgstr is valid, False otherwise.
        """

        valid = True

        def print_error(msg):
            print(f"msgid: {msgid}")
            print(f"msgstr: {msgstr}")
            print(msg)

        # 1. Escaping
        if re.search(r'(?<!\\)"', msgstr) or re.search(r'(?<!\\)\\', msgstr):
            print_error("Error: msgstr contains unescaped double quotes or backslashes.")
            valid = False

        # 2. Placeholders
        msgid_placeholders = re.findall(r'%[sdif]|{.*?}', msgid)  # Find all placeholders
        msgstr_placeholders = re.findall(r'%[sdif]|{.*?}', msgstr)

        if len(msgid_placeholders) != len(msgstr_placeholders) or \
                any(msgid_placeholders[i] != msgstr_placeholders[i] for i in range(len(msgid_placeholders))):
            print_error("Error: msgstr placeholders do not match msgid placeholders.")
            valid = False

        # 3. Encoding (basic check)
        try:
            msgstr.encode('utf-8')
        except UnicodeEncodeError:
            print_error("Error: msgstr is not valid UTF-8.")
            valid = False

        # 4. Line continuation (basic check)
        if msgstr.count('\n') != msgstr.count(r'\n'):  # Checking if newlines are escaped.
            if msgstr.count('\n') > 0 and not msgstr.startswith('"'):
                print_error("Error: msgstr contains unescaped newlines and does not start with double quote.")
                valid = False

        return valid

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
