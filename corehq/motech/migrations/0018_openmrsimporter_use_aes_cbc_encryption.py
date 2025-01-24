from django.db import migrations
from django.db.migrations import RunPython

from corehq.dbaccessors.couchapps.all_docs import get_doc_ids_by_class
from corehq.motech.const import ALGO_AES_CBC
from corehq.util.couch import DocUpdate, iter_update
from corehq.util.django_migrations import skip_on_fresh_install
from corehq.util.log import with_progress_bar
from corehq.motech.openmrs.models import OpenmrsImporter
from corehq.motech.utils import (
    reencrypt_ecb_to_cbc_mode,
    reencrypt_cbc_to_ecb_mode,
)


@skip_on_fresh_install
def reencrypt_openmrsimporters_passwords(apps, schema_editor):
    app_ids = get_doc_ids_by_class(OpenmrsImporter)
    iter_update(OpenmrsImporter.get_db(), _reencrypt_password, with_progress_bar(app_ids))


def _reencrypt_password(app_doc):
    original_password = app_doc['password']
    if original_password.startswith(f'${ALGO_AES_CBC}$'):
        return DocUpdate(app_doc)
    else:
        app_doc['password'] = reencrypt_ecb_to_cbc_mode(original_password)
    return DocUpdate(app_doc)


def revert_reencrypt_openmrsimporters_passwords(apps, schema_editor):
    app_ids = get_doc_ids_by_class(OpenmrsImporter)
    iter_update(OpenmrsImporter.get_db(), _revert_reencrypt_password,
                with_progress_bar(app_ids))


def _revert_reencrypt_password(app_doc):
    original_password = app_doc['password']
    if original_password.startswith(f'${ALGO_AES_CBC}$'):
        encrypted_password = reencrypt_cbc_to_ecb_mode(original_password, f'${ALGO_AES_CBC}$')
        app_doc['password'] = encrypted_password.split('$', 2)[2]
    return DocUpdate(app_doc)


class Migration(migrations.Migration):

    dependencies = [
        ('motech', '0017_connectionsettings_use_aes_cbc_encryption'),
    ]

    operations = [
        RunPython(reencrypt_openmrsimporters_passwords,
                  revert_reencrypt_openmrsimporters_passwords),
    ]
