from time import sleep
import polib
import os
import hashlib
from openai import OpenAI
import json
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
import gevent


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
    for key, translated_str in translated_strings.items():
        po_translation_obj = translation_map.get(key, None)
        if po_translation_obj:
            po_translation_obj.msgstr = translated_str
        else:
            # In few cases, the LLMs return a hash that is slightly different from the original hash
            # In this case, we will just skip the translation.
            # We will try to re-run the script again to get around with this issue.
            print(f"Translation object not found for key: {key} | {translated_str}")
    all_translations.save()


def translate_batch(client, batch, lang, model):
    print(f"Translating batch of {len(batch)} strings")
    # Simplified system prompt
    system_prompt = (
        f"Translate the following texts to {lang}. Keep the structure and formatting. "
        "Do not translate placeholders in curly braces, Python %-style strings, HTML tags, or URLs. "
        "Ensure translated text maintains leading/trailing newlines. "
        "Input: JSON array of objects with unique hash and message. "
        "Response: JSON object on the following format: "
        "{\"hash\":\"translated_message\", \"hash\":\"translated_message\", ...}"
        "Use double quotes and escape newlines."
    )
    batch_str = json.dumps(batch)
    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": batch_str}
        ],
        temperature=0.2,
        response_format={
            "type": "json_object",
        },
    )
    try:
        return json.loads(completion.choices[0].message.content)
    except Exception as e:
        # Fine to skip the batch if the LLM does not return a valid JSON
        # We will try to re-run the script again to get around with this issue.
        print(f"Error translating batch: {e}")
        print(completion.choices[0].message.content)
        return {}


def create_dict_batch(entire_dict, batch_size):
    dict_keys = list(entire_dict.keys())
    dict_batches = []
    for i in range(0, len(dict_keys), batch_size):
        batch_keys = dict_keys[i:i + batch_size]
        dict_batches.append([{key: entire_dict[key].msgid} for key in batch_keys])
    return dict_batches


def compile_po_file(po_file_path):
    po = polib.pofile(po_file_path)
    mo_file_path = po_file_path.replace('.po', '.mo')
    po.save_as_mofile(mo_file_path)
    print(f"Compiled MO file saved at: {mo_file_path}")


def run_main(batch_size=10, env='dev', lang='fr'):
    # TODO: Get the list of languages from the settings
    # TODO: add support for plural strings
    # TODO: integrate it into the build process
    # TODO: Add verification model
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
        print(f"Translating {po_file}")
        all_translations = polib.pofile(po_file)
        untranslated_entries = _filter_untranslated_objects(all_translations)
        translations_to_process = len(untranslated_entries)
        translation_map = build_translation_obj_map(untranslated_entries)

        print(f"Total translations {translations_to_process} ")
        dict_batches = create_dict_batch(translation_map, batch_size)
        translated_strings = dict()
        translation_calls = []
        iteration = 0
        for batch in dict_batches:
            iteration += 1
            sleep(2)
            translation_calls.append(
                gevent.spawn(translate_batch, client, batch, lang, model)
            )
        gevent.joinall(translation_calls)
        results = [call.value for call in translation_calls]
        for result in results:
            translated_strings = translated_strings | result
        add_translations_to_file(translated_strings, translation_map, all_translations)
        # Add logic to compile the po file
        compile_po_file(po_file)


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
