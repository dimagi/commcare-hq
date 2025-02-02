from django.db import migrations
from django.db.migrations import RunPython

from corehq.motech.const import ALGO_AES, ALGO_AES_CBC
from corehq.util.django_migrations import skip_on_fresh_install
from corehq.motech.utils import (
    reencrypt_ecb_to_cbc_mode,
    reencrypt_cbc_to_ecb_mode,
    b64_aes_cbc_encrypt,
)


@skip_on_fresh_install
def migrate_tableau_connected_app_secret_value(apps, schema_editor):
    TableauConnectedApp = apps.get_model('reports', 'TableauConnectedApp')

    connected_apps_to_update = TableauConnectedApp.objects.exclude(
        encrypted_secret_value__startswith=f'${ALGO_AES_CBC}$'
    ).exclude(encrypted_secret_value=None).exclude(encrypted_secret_value='')

    for connected_app in connected_apps_to_update:
        encrypted_secret_value = connected_app.encrypted_secret_value
        if encrypted_secret_value.startswith(f'${ALGO_AES}$'):
            connected_app.encrypted_secret_value = reencrypt_ecb_to_cbc_mode(
                encrypted_secret_value, f'${ALGO_AES}$'
            )
        else:
            ciphertext = b64_aes_cbc_encrypt(encrypted_secret_value)
            connected_app.encrypted_secret_value = f'${ALGO_AES_CBC}${ciphertext}'
        connected_app.save()


def revert_tableau_connected_app_secret_value(apps, schema_editor):
    TableauConnectedApp = apps.get_model('reports', 'TableauConnectedApp')

    connected_apps_to_revert = TableauConnectedApp.objects.filter(
        encrypted_secret_value__startswith=f'${ALGO_AES_CBC}$'
    )

    for connected_app in connected_apps_to_revert:
        connected_app.encrypted_secret_value = reencrypt_cbc_to_ecb_mode(
            connected_app.encrypted_secret_value, f'${ALGO_AES_CBC}$'
        )
        connected_app.save()


class Migration(migrations.Migration):

    dependencies = [
        ('reports', '0020_tableauserver_get_reports_using_role'),
    ]

    operations = [
        RunPython(migrate_tableau_connected_app_secret_value,
                  reverse_code=revert_tableau_connected_app_secret_value),
    ]
