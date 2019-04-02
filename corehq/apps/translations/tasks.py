from __future__ import absolute_import
from __future__ import unicode_literals

import os
import sys
import six
from io import open
from zipfile import ZipFile

from celery.task import task
from django.conf import settings
from django.core.files.temp import NamedTemporaryFile
from django.core.mail.message import EmailMessage

from corehq.apps.translations.integrations.transifex.transifex import Transifex


@task(serializer='pickle')
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
    email = EmailMessage(
        subject='[{}] - Transifex removed translations'.format(settings.SERVER_ENVIRONMENT),
        body=(result_note +
              "\n".join([' '.join([sheet_name, result]) for sheet_name, result in delete_status.items()])
              ),
        to=[email],
        from_email=settings.DEFAULT_FROM_EMAIL
    )
    email.send()


@task(serializer='pickle')
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
        email = EmailMessage(
            subject='[{}] - Transifex pushed translations'.format(settings.SERVER_ENVIRONMENT),
            body=(result_note +
                  "\n".join([' '.join([sheet_name, result]) for sheet_name, result in upload_status.items()])
                  ),
            to=[email],
            from_email=settings.DEFAULT_FROM_EMAIL
        )
        email.send()


@task(serializer='pickle')
def pull_translation_files_from_transifex(domain, data, user_email=None):
    def notify_error(error):
        email = EmailMessage(
            subject='[{}] - Transifex pulled translations'.format(settings.SERVER_ENVIRONMENT),
            body="The request could not be completed. Something went wrong with the download. "
                 "Error raised : {}. "
                 "If you see this repeatedly and need support, please report an issue. ".format(error),
            to=[user_email],
            from_email=settings.DEFAULT_FROM_EMAIL
        )
        email.send()
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
            email = EmailMessage(
                subject='[{}] - Transifex pulled translations'.format(settings.SERVER_ENVIRONMENT),
                body="PFA Translations pulled from transifex.",
                to=[user_email],
                from_email=settings.DEFAULT_FROM_EMAIL
            )
            email.attach(filename=filename, content=file_obj.read())
            email.send()
    except Exception as e:
        notify_error(e)
        six.reraise(*sys.exc_info())
    finally:
        if translation_file and os.path.exists(translation_file.name):
            os.remove(translation_file.name)


@task(serializer='pickle')
def backup_project_from_transifex(domain, data, email):
    version = data.get('version')
    transifex = Transifex(domain,
                          data.get('app_id'),
                          data.get('source_lang'),
                          data.get('transifex_project_slug'),
                          version,
                          use_version_postfix='yes' in data['use_version_postfix'])
    project_details = transifex.client.project_details().json()
    target_lang_codes = project_details.get('teams')
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
        email = EmailMessage(
            subject='[{}] - Transifex backup translations'.format(settings.SERVER_ENVIRONMENT),
            body="PFA Translations backup from transifex.",
            to=[email],
            from_email=settings.DEFAULT_FROM_EMAIL
        )
        filename = "%s-TransifexBackup.zip" % project_details.get('name')
        email.attach(filename=filename, content=tmp.read())
        email.send()
