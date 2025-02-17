import polib
import os
import hashlib
from openai import OpenAI
import json
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


def get_hash(msg):
    return hashlib.md5(msg.encode('utf-8')).hexdigest()


def _filter_untranslated_objects(all_translations):
    return [message_obj for message_obj in all_translations if not message_obj.translated()]


def _filter_translations_with_plural_strings(translations):
    return [message_obj for message_obj in translations if message_obj.msgid_plural]


def _filter_translations_with_oneline_strings(translations):
    return [message_obj for message_obj in translations if len(message_obj.msgid.split('\n')) == 1]


def _filter_translations_with_multiline_strings(translations):
    return [message_obj for message_obj in translations if len(message_obj.msgid.split('\n')) > 1]


def build_translation_obj_map(translations):
    translation_obj_map = {}
    for message_obj in translations:
        key = get_hash(message_obj.msgid)
        translation_obj_map[key] = message_obj
    return translation_obj_map


def add_translations_to_file(translated_strings, translation_map, all_translations):
    for entry in translated_strings:
        key, translated_str = entry
        po_translation_obj = translation_map[key]
        po_translation_obj.msgstr = translated_str
    all_translations.save()


def translate_batch(client, batch, lang, model):
    system_prompt = (
        f"You are a professional translator. Translate the following texts to {lang}."
        """Maintain the exact same structure and formatting. Do not translate any placeholders enclosed in
        curly braces(e.g. {example}), Python %-style formatting strings (e.g. %(name)s), HTML tags, or URLs.
        If the original text starts with a newline,
        ensure the translated text also starts with an escaped newline(i.e. "\\n").
        Similarly, if the original text ends with a newline, ensure the translation ends with an escaped newline.

        You will be provided a JSON array of objects,
        where each object contains a single key-value pair with a unique hash and its corresponding message.
        For example:
        [
            {"hash_1": "message 1"},
            {"hash_2": "message 2"}
        ]

        Translate each message and return your result strictly as valid JSON with the following format:

        [
            ["hash_1", "translated message 1"],
            ["hash_2", "translated message 2"]
        ]

        Important:

        Use double quotes for all JSON keys and string values.
        Ensure that any double quotes within the translated messages are properly escaped (e.g. use \\").
        All newline characters within messages must be escaped as \\n.
        Do not include any additional text, explanation,
        or markdown formatting in your output. Return only the JSON.
    """)

    batch_str = json.dumps(batch)
    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": batch_str}
        ],
        temperature=0.2,
    )
    return json.loads(completion.choices[0].message.content)


def create_dict_batch(entire_dict, batch_size):
    dict_keys = list(entire_dict.keys())
    for i in range(0, len(dict_keys), batch_size):
        batch_keys = dict_keys[i:i + batch_size]
        yield [{key: entire_dict[key].msgid} for key in batch_keys]


def run_main(batch_size=10, env='dev', lang='fr'):
    locale_path = os.path.join(settings.BASE_DIR, 'locale')
    po_file_path = os.path.join(locale_path, lang, 'LC_MESSAGES', 'django.po')
    pojs_file_path = os.path.join(locale_path, lang, 'LC_MESSAGES', 'djangojs.po')
    params = {
        'api_key': 'lm-studio',
        'base_url': "http://localhost:1234/v1"
    }
    model = "mradermacher/Meta-Llama-3.1-8B-Instruct_CODE_Python_English_Asistant-16bit-v2-GGUF"
    if env == 'prod':
        params = {'api_key': settings.OPENAI_API_KEY}
        model = 'gpt-4o-mini'
        client = OpenAI(**params)

        for po_file in [po_file_path, pojs_file_path]:
            all_translations = polib.pofile(po_file)
            untranslated_entries = _filter_untranslated_objects(all_translations)
            translations_to_process = len(untranslated_entries)
            translation_map = build_translation_obj_map(untranslated_entries)

            print(f"Total translations {translations_to_process} ")
            translated = 0
            for batch in create_dict_batch(translation_map, batch_size):
                translated_strings = translate_batch(client, batch, lang, model)
                translated += len(translated_strings)
                add_translations_to_file(translated_strings, translation_map, all_translations)
                print(f"added {translated} strings | remaining {translations_to_process-translated}")


class Command(BaseCommand):
    help = 'Translate untranslated strings in .po files using OpenAI API'

    def add_arguments(self, parser):
        parser.add_argument(
            '--batch-size',
            type=int,
            default=10,
            help='Number of strings to translate in each API call'
        )
        parser.add_argument(
            '--env',
            type=str,
            default='dev',
            choices=['dev', 'prod'],
            help='Environment to run in (dev uses local LM Studio, prod uses OpenAI)'
        )
        parser.add_argument(
            '--lang',
            type=str,
            default='fr',
            help='Target language code (e.g. fr, es)'
        )

    def handle(self, *args, **options):
        try:
            run_main(
                batch_size=options['batch_size'],
                env=options['env'],
                lang=options['lang']
            )
        except Exception as e:
            print(e)
            raise CommandError(f'Translation failed: {str(e)}')
