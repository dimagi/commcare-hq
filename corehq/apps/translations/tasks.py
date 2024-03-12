import os
import sys
from zipfile import ZipFile

from django.conf import settings
from django.core.files.temp import NamedTemporaryFile
from django.template.defaultfilters import linebreaksbr

import six

from corehq.apps.celery import task
from corehq.apps.hqwebapp.tasks import send_mail_async
from corehq.apps.translations.generators import AppTranslationsGenerator
from corehq.apps.translations.integrations.transifex.parser import (
    TranslationsParser,
)
from corehq.apps.translations.integrations.transifex.project_migrator import (
    ProjectMigrator,
)
from corehq.apps.translations.integrations.transifex.transifex import Transifex


@task
def delete_resources_on_transifex(domain, data, email):
    version = data.get('version')
    transifex = Transifex(domain,
                          data.get('app_id'),
                          data.get('target_lang') or data.get('source_lang'),
                          data.get('transifex_project_slug'),
                          version,
                          use_version_postfix='yes' in data['use_version_postfix'])
    delete_status = transifex.delete_resources()
    result_note = "Hi,\nThe request to delete resources for app {app_id}(version {version}), " \
                  "was completed on project {transifex_project_slug} on transifex. " \
                  "The result is as follows:\n".format(**data)

    subject = '[{}] - Transifex removed translations'.format(settings.SERVER_ENVIRONMENT)
    body = (result_note
            + "\n".join([' '.join([sheet_name, result])for sheet_name, result in delete_status.items()])
            )
    send_mail_async.delay(
        subject, body,
        recipient_list=[email],
        domain=domain,
        use_domain_gateway=True,
    )


@task
def push_translation_files_to_transifex(domain, data, email):
    upload_status = None
    if data.get('target_lang'):
        upload_status = Transifex(domain,
                                  data.get('app_id'),
                                  data.get('target_lang'),
                                  data.get('transifex_project_slug'),
                                  data.get('version'),
                                  is_source_file=False,
                                  exclude_if_default=True,
                                  use_version_postfix='yes' in data['use_version_postfix']
                                  ).send_translation_files()
    elif data.get('source_lang'):
        upload_status = Transifex(domain,
                                  data.get('app_id'),
                                  data.get('source_lang'),
                                  data.get('transifex_project_slug'),
                                  data.get('version'),
                                  use_version_postfix='yes' in data['use_version_postfix'],
                                  update_resource=(data['action'] == 'update')
                                  ).send_translation_files()
    data['language'] = data.get('target_lang') or data.get('source_lang')
    if upload_status:
        result_note = "Hi,\nThe upload for app {app_id}(version {version}), " \
                      "for language '{language}' " \
                      "was completed on project {transifex_project_slug} on transifex. " \
                      "The result is as follows:\n".format(**data)

        subject = '[{}] - Transifex pushed translations'.format(settings.SERVER_ENVIRONMENT)
        body = (result_note
                + "\n".join([' '.join([sheet_name, result]) for sheet_name, result in upload_status.items()])
                )
        send_mail_async.delay(
            subject, body,
            recipient_list=[email],
            domain=domain,
            use_domain_gateway=True,
        )


@task
def pull_translation_files_from_transifex(domain, data, user_email=None):
    def notify_error(error):
        subject = '[{}] - Transifex pulled translations'.format(settings.SERVER_ENVIRONMENT)
        body = (
            "The request could not be completed. Something went wrong with the download. "
            "Error raised: {}. "
            "If you see this repeatedly and need support, please report an issue.".format(error)
        )
        send_mail_async.delay(
            subject, body,
            recipient_list=[user_email],
            domain=domain,
            use_domain_gateway=True,
        )
    version = data.get('version')
    transifex = Transifex(domain,
                          data.get('app_id'),
                          data.get('target_lang') or data.get('source_lang'),
                          data.get('transifex_project_slug'),
                          version,
                          lock_translations=data.get('lock_translations'),
                          use_version_postfix='yes' in data['use_version_postfix'])
    translation_file = None
    try:
        translation_file, filename = transifex.generate_excel_file()
        with open(translation_file.name, 'rb') as file_obj:
            send_mail_async(
                subject='[{}] - Transifex pulled translations'.format(settings.SERVER_ENVIRONMENT),
                message="PFA Translations pulled from transifex.",
                recipient_list=[user_email],
                filename=filename,
                content=file_obj.read(),
                domain=domain,
                use_domain_gateway=True,
            )
    except Exception as e:
        notify_error(e)
        six.reraise(*sys.exc_info())
    finally:
        if translation_file and os.path.exists(translation_file.name):
            os.remove(translation_file.name)


@task
def backup_project_from_transifex(domain, data, email):
    version = data.get('version')
    transifex = Transifex(domain,
                          data.get('app_id'),
                          data.get('source_lang'),
                          data.get('transifex_project_slug'),
                          version,
                          use_version_postfix='yes' in data['use_version_postfix'])
    project_name = transifex.client.project_name
    target_lang_codes = transifex.client.get_project_langcodes()
    with NamedTemporaryFile(mode='w+b', suffix='.zip') as tmp:
        with ZipFile(tmp, 'w') as zipfile:
            for target_lang in target_lang_codes:
                transifex = Transifex(domain,
                                      data.get('app_id'),
                                      target_lang,
                                      data.get('transifex_project_slug'),
                                      version,
                                      use_version_postfix='yes' in data['use_version_postfix'])
                translation_file, filename = transifex.generate_excel_file()
                with open(translation_file.name, 'rb') as file_obj:
                    zipfile.writestr(filename, file_obj.read())
                os.remove(translation_file.name)
        tmp.seek(0)
        send_mail_async(
            subject='[{}] - Transifex backup translations'.format(settings.SERVER_ENVIRONMENT),
            body="PFA Translations backup from transifex.",
            recipient_list=[email],
            filename="%s-TransifexBackup.zip" % project_name,
            content=tmp.read(),
            domain=domain,
            use_domain_gateway=True,
        )


@task
def email_project_from_hq(domain, data, email):
    """Emails the requester with an excel file translations to be sent to Transifex.

    Used to verify translations before sending to Transifex
    """
    lang = data.get('source_lang')
    project_slug = data.get('transifex_project_slug')
    quacks_like_a_transifex = AppTranslationsGenerator(domain, data.get('app_id'), data.get('version'),
                                                       key_lang=lang, source_lang=lang, lang_prefix='default_')
    parser = TranslationsParser(quacks_like_a_transifex)
    try:
        translation_file, __ = parser.generate_excel_file()
        with open(translation_file.name, 'rb') as file_obj:
            send_mail_async(
                subject='[{}] - HQ translation download'.format(settings.SERVER_ENVIRONMENT),
                message="Translations from HQ",
                recipient_list=[email],
                filename="{project}-{lang}-translations.xls".format(project=project_slug, lang=lang),
                content=file_obj.read(),
                domain=domain,
                use_domain_gateway=True,
            )
    finally:
        try:
            os.remove(translation_file.name)
        except (NameError, OSError):
            pass


@task
def migrate_project_on_transifex(domain, transifex_project_slug, source_app_id, target_app_id, mappings, email):
    def consolidate_errors_messages():
        error_messages = []
        for old_id, response in slug_update_responses.items():
            if response.status_code != 200:
                error_messages.append("Slug update failed for %s with message %s" % (old_id, response.content))
        for lang_code, response in menus_and_forms_sheet_update_responses.items():
            if response.status_code != 200:
                error_messages.append(
                    "Menus and forms sheet update failed for lang %s with message %s" % (
                        lang_code, response.content))
        return error_messages

    def generate_email_body():
        error_messages = consolidate_errors_messages()
        email_body = "Transifex project migration completed for project %s.\n" % transifex_project_slug
        if error_messages:
            email_body += "Following issues were encountered during update:\n"
            for error_message in error_messages:
                email_body += error_message + "\n"
        return email_body

    slug_update_responses, menus_and_forms_sheet_update_responses = ProjectMigrator(
        domain,
        transifex_project_slug,
        source_app_id, target_app_id,
        mappings
    ).migrate()

    send_mail_async(
        subject='[{}] - Transifex Project Migration Status'.format(settings.SERVER_ENVIRONMENT),
        body=linebreaksbr(generate_email_body()),
        recipient_list=[email],
        domain=domain,
        use_domain_gateway=True,
    )
