import gettext
import json
import os
import re
import subprocess
import sys
from functools import cached_property

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

import gevent
import polib

from corehq.apps.translations.integrations.llm import (
    OpenaiTranslator,
    TranslationFormat,
)

# Counts tried when working out which numbers each plural index is used for
PLURAL_SAMPLE_COUNTS = list(range(0, 201)) + [1000, 1000000, 2000000]

# English-style rule used when a header has no ``plural=``: index 0 for
# exactly one, index 1 for every other count. Pairs with nplurals=2.
DEFAULT_PLURAL_EXPRESSION = "n != 1"


def nplurals_from_header(plural_forms_header):
    """
    Return how many ``msgstr[N]`` plural indices a PO file's ``Plural-Forms``
    header entry declares, or 2 (English-style singular and plural) when the
    header doesn't say.

    >>> nplurals_from_header("nplurals=3; plural=(n==1 ? 0 : n==2 ? 1 : 2);")
    3
    >>> nplurals_from_header("")
    2
    """
    match = re.search(r'nplurals\s*=\s*(\d+)', plural_forms_header)
    return int(match.group(1)) if match else 2


def plural_index_function_from_header(plural_forms_header):
    """
    Return a function mapping a count ``n`` to the ``msgstr[N]`` index used
    for it, built from the ``plural=`` expression in a PO file's
    ``Plural-Forms`` header entry.

    The expression is written in C syntax, e.g.
    ``plural=(n%10==1 && n%100!=11 ? 0 : 1);``. ``gettext.c2py`` ("C to
    Python") is the standard library helper that ``ngettext`` itself uses to
    turn it into a Python function. It accepts only ``n``, numbers and operators, and
    raises ``ValueError`` for anything else.

    >>> plural_index_for = plural_index_function_from_header("nplurals=2; plural=(n != 1);")
    >>> plural_index_for(1), plural_index_for(5)
    (0, 1)
    """
    match = re.search(r'plural\s*=\s*([^;]+)', plural_forms_header)
    plural_expression = match.group(1) if match else DEFAULT_PLURAL_EXPRESSION
    return gettext.c2py(plural_expression)


def counts_by_plural_index_from_header(plural_forms_header):
    """
    Map each plural index to the sample counts that select it, according to
    a PO file's ``Plural-Forms`` header entry.

    >>> counts = counts_by_plural_index_from_header("nplurals=2; plural=(n != 1);")
    >>> counts[0], counts[1][:4]
    ([1], [0, 2, 3, 4])
    """
    plural_index_for = plural_index_function_from_header(plural_forms_header)
    counts = {plural_index: [] for plural_index in range(nplurals_from_header(plural_forms_header))}
    for n in PLURAL_SAMPLE_COUNTS:
        counts[plural_index_for(n)].append(n)
    return counts


# C0 control characters other than tab, newline and carriage return, plus DEL.
# The LLM sometimes turns escapes like "\u2014" into "\u0014", which msgfmt
# accepts.
CONTROL_CHARS_RE = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')


def has_control_chars(msgid, msgstr):
    return bool(set(CONTROL_CHARS_RE.findall(msgstr)) - set(CONTROL_CHARS_RE.findall(msgid)))


# msgfmt errors look like "<file>.po:<line>: <message>"
MSGFMT_ERROR_RE = re.compile(r'^.+\.po:(\d+):\s*(.*)$')


class PoTranslationFormat(TranslationFormat):
    """
    Translation format for PO files. The class expects gettext installed in the system.
    As it uses gettext's msgfmt command to check for errors in the PO file.

    Plural entries (``msgid_plural``) are sent to the LLM as an object describing
    each plural index of the target language, and the translation for each index
    comes back as a separate ``"<key>:<plural index>"`` key, so the response stays
    a flat map of strings.
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
        return [
            msg for msg in self.all_message_objects
            if msg.fuzzy or not self._is_translated(msg) or has_control_chars(msg.msgid, msg.msgstr)
        ]

    def _is_translated(self, msg):
        if msg.msgid_plural:
            return all(msg.msgstr_plural.get(plural_index) for plural_index in range(self.nplurals))
        return msg.msgstr != ""

    @cached_property
    def _plural_forms_header(self):
        return self.all_message_objects.metadata.get('Plural-Forms', '')

    @cached_property
    def nplurals(self):
        return nplurals_from_header(self._plural_forms_header)

    @cached_property
    def counts_by_plural_index(self):
        """
        Map each plural index to the sample counts that select it, e.g.
        ``{0: [1], 1: [0, 2, 3, ...]}`` for ``plural=(n != 1)``.
        """
        return counts_by_plural_index_from_header(self._plural_forms_header)

    def _plural_index_description(self, plural_index):
        counts = self.counts_by_plural_index[plural_index]
        if not counts:
            return "not used for whole numbers (e.g. fractions); use the general plural"
        examples = ", ".join(str(n) for n in counts[:8])
        return f"used when n is {examples}{', ...' if len(counts) > 8 else ''}"

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
            if message_obj.msgid_plural:
                batch_dict[index] = {
                    "singular": message_obj.msgid,
                    "plural": message_obj.msgid_plural,
                    "forms": {
                        str(plural_index): self._plural_index_description(plural_index)
                        for plural_index in range(self.nplurals)
                    },
                }
            else:
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
            filtered_output = {}
            for index, message_obj in self.translation_obj_map.items():
                if message_obj.msgid_plural:
                    msgstrs = self._parse_plural_msgstrs(index, message_obj, llm_output)
                    if msgstrs is not None:
                        filtered_output[index] = msgstrs
                elif index in llm_output and self.is_valid_msgstr(message_obj.msgid, llm_output[index]):
                    filtered_output[index] = llm_output[index]
            self.fill_translations(filtered_output)
            return filtered_output
        except json.JSONDecodeError:
            """There have been cases when the output returned by llm is not a valid json object.
            In that case, we will return an empty dict.
            And it is safe to do it because the untranslated messages will
            be translated in the next run of the script.
            """
            return {}

    def _parse_plural_msgstrs(self, index, message_obj, llm_output):
        """
        Return ``{plural index: msgstr}`` for a plural entry, or None unless every
        plural index is present and valid. An index used only for n == 1 is
        checked against the singular msgid, every other one against the plural.
        """
        msgstrs = {}
        for plural_index in range(self.nplurals):
            msgstr = llm_output.get(f"{index}:{plural_index}")
            if not isinstance(msgstr, str) or not msgstr:
                return None
            is_singular = self.counts_by_plural_index[plural_index] == [1]
            source = message_obj.msgid if is_singular else message_obj.msgid_plural
            if not self.is_valid_msgstr(source, msgstr):
                return None
            msgstrs[plural_index] = msgstr
        return msgstrs

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

        # 4. Control characters
        if has_control_chars(msgid, msgstr):
            print_error(f"Control characters in msgstr: {CONTROL_CHARS_RE.findall(msgstr)}")
            return False

        # 5. Encoding
        try:
            msgstr.encode('utf-8')
        except UnicodeEncodeError as e:
            print_error(f"Invalid UTF-8 encoding: {e}")
            return False
        return True

    def fill_translations(self, llm_output):
        for index, msg_str in llm_output.items():
            msg_obj = self.translation_obj_map[index]
            if msg_obj.msgid_plural:
                # Replace every plural index, including ones already translated:
                # a partly translated entry usually means the Plural-Forms header
                # gained an index, which can change what the existing ones mean
                msg_obj.msgstr_plural = msg_str
            else:
                msg_obj.msgstr = msg_str
            if msg_obj.fuzzy:
                # no longer fuzzy, translated by AI
                msg_obj.flags.remove('fuzzy')

    def save_output(self):
        """
        Save the translations to the PO file.
        """
        self.all_message_objects.save()

    def format_input_description(self):
        return "- Ensure that translations are gender neutral unless the original text is gender specific. " \
               "- Do not translate placeholders in curly braces, Python %-style strings, HTML tags, or URLs. " \
               "- Ensure translated text maintains leading/trailing newlines. " \
               "- Every translated message should be valid `msgstr` and should adhere to all of its specs. " \
               "- Special characters like double quotes (\") and backslashes (\\) must be escaped " \
               "with a backslash. " \
               "Input: a JSON object mapping a key to the message to translate, e.g. " \
               "{\"0\": \"msgid\", \"1\": \"msgid\", ...}. " \
               "Some values are plural messages instead of strings: " \
               "{\"singular\": \"text for one\", \"plural\": \"text for many\", " \
               "\"forms\": {\"0\": \"used when n is ...\", \"1\": \"used when n is ...\"}}. " \
               "Translate a plural message once per entry in \"forms\", choosing the grammatical " \
               "form the target language uses for those numbers. A form used only when n is 1 " \
               "keeps the placeholders of the singular text; every other form keeps those of " \
               "the plural text."

    def format_output_description(self):
        return "Response: JSON object on the following format: " \
               "{\"0\":\"translated_message for key 0\", \"1\":\"translated_message for key 1\", ...}. " \
               "For a plural message, return one key per form instead of the plain key: " \
               "{\"<key>:0\": \"form 0 translation\", \"<key>:1\": \"form 1 translation\", ...}"

    def check_and_remove_errored_messages(self, lang_path):
        """
        Checks PO files using gettext's msgfmt and removes translations that are problematic.
        These problematic translations are those that cause errors during compilemessages or runtime.
        """
        self._remove_control_char_translations()
        error_output = self._run_msgfmt(lang_path)
        if not error_output:
            print(f"No errors found in the PO file - {lang_path}")
            return
        line_num_error_map = self._extract_errored_msgstr_ids(error_output)
        if line_num_error_map:
            self._remove_errored_translations(line_num_error_map)

    def _remove_control_char_translations(self):
        """
        Clears msgstrs containing control characters that are not in the msgid.
        msgfmt accepts these, so they would otherwise ship whenever
        re-translating them fails.
        """
        all_translations = polib.pofile(self.file_path)
        count = 0
        for entry in all_translations:
            if has_control_chars(entry.msgid, entry.msgstr):
                print(f"Removing translation with control characters for msgid: {entry.msgid}")
                entry.msgstr = ""
                count += 1
        if count > 0:
            all_translations.save()
            print(f"Removed {count} translations with control characters")

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
            # Only trust lines that point at a PO file line. Anything else, like
            # lines without a line number ("<file>: warning: Charset missing in
            # header.") or stray output from native libraries in the subprocess
            # ("…/driver.rs:196:23: …"), must not map to a msgstr.
            match = MSGFMT_ERROR_RE.match(line)
            if not match:
                continue
            line_num, message = match.groups()
            if message.startswith('warning'):
                continue
            line_num_error_map[int(line_num)] = message.strip()
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
                    print(f"msgstr: {entry.msgstr_plural if entry.msgid_plural else entry.msgstr}")
                    print("--------------------------------")
                    if entry.msgid_plural:
                        # Plural entries store their translations in msgstr_plural,
                        # not msgstr, so blank every msgstr[N] to actually clear it.
                        entry.msgstr_plural = {k: "" for k in entry.msgstr_plural}
                    else:
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
