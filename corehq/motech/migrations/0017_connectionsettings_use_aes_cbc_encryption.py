from django.db import migrations
from django.db.migrations import RunPython

from corehq.motech.const import ALGO_AES, ALGO_AES_CBC
from corehq.util.django_migrations import skip_on_fresh_install
from corehq.motech.utils import (
    reencrypt_ecb_to_cbc_mode,
    reencrypt_cbc_to_ecb_mode,
    b64_aes_cbc_encrypt,
    AesEcbDecryptionError
)


@skip_on_fresh_install
def migrate_api_settings(apps, schema_editor):
    ConnectionSettings = apps.get_model("motech", "ConnectionSettings")

    connect_settings_to_update = ConnectionSettings.objects.exclude(
        password__startswith=f'${ALGO_AES_CBC}$',
        client_secret__startswith=f'${ALGO_AES_CBC}$',
        last_token_aes__startswith=f'${ALGO_AES_CBC}$',
    ).exclude(
        password='',
        client_secret='',
        last_token_aes=''
    )

    for connection in connect_settings_to_update:
        connection.password = _reencrypted_password_with_cbc(connection)
        connection.client_secret = _reencrypted_client_secret_with_cbc(connection)
        connection.last_token_aes = _reencrypted_last_token_with_cbc(connection)
        connection.save()


def _reencrypted_password_with_cbc(connection):
    if connection.password == '':
        return ''
    elif connection.password.startswith(f'${ALGO_AES}$'):
        try:
            return reencrypt_ecb_to_cbc_mode(connection.password, f'${ALGO_AES}$')
        except AesEcbDecryptionError:
            return ''
    else:
        ciphertext = b64_aes_cbc_encrypt(connection.password)
        return f'${ALGO_AES_CBC}${ciphertext}'


def _reencrypted_client_secret_with_cbc(connection):
    if connection.client_secret == '':
        return ''
    elif connection.client_secret.startswith(f'${ALGO_AES}$'):
        try:
            return reencrypt_ecb_to_cbc_mode(connection.client_secret, f'${ALGO_AES}$')
        except AesEcbDecryptionError:
            return ''
    else:
        ciphertext = b64_aes_cbc_encrypt(connection.client_secret)
        return f'${ALGO_AES_CBC}${ciphertext}'


def _reencrypted_last_token_with_cbc(connection):
    if connection.last_token_aes == '':
        return ''
    elif connection.last_token_aes.startswith(f'${ALGO_AES}$'):
        prefix = f'${ALGO_AES}$'
    else:
        prefix = None
    try:
        return reencrypt_ecb_to_cbc_mode(connection.last_token_aes, prefix)
    except AesEcbDecryptionError:
        return ''


def revert_api_settings(apps, schema_editor):
    ConnectionSettings = apps.get_model("motech", "ConnectionSettings")

    connect_settings_to_revert = ConnectionSettings.objects.exclude(
        password__startswith=f'${ALGO_AES}$',
        client_secret__startswith=f'${ALGO_AES}$',
        last_token_aes__startswith=f'${ALGO_AES}$',
    ).exclude(
        password='',
        client_secret='',
        last_token_aes=''
    )

    for connection in connect_settings_to_revert:
        connection.password = _revert_reencrypted_password_with_ecb(connection)
        connection.client_secret = _revert_reencrypted_client_secret_with_ecb(connection)
        connection.last_token_aes = _revert_reencrypted_last_token_with_ecb(connection)
        connection.save()


def _revert_reencrypted_password_with_ecb(connection):
    if connection.password == '':
        return ''
    elif connection.password.startswith(f'${ALGO_AES_CBC}$'):
        return reencrypt_cbc_to_ecb_mode(connection.password, f'${ALGO_AES_CBC}$')
    else:
        return connection.password


def _revert_reencrypted_client_secret_with_ecb(connection):
    if connection.client_secret == '':
        return ''
    elif connection.client_secret.startswith(f'${ALGO_AES_CBC}$'):
        return reencrypt_cbc_to_ecb_mode(connection.client_secret, f'${ALGO_AES_CBC}$')
    else:
        return connection.client_secret


def _revert_reencrypted_last_token_with_ecb(connection):
    if connection.last_token_aes == '':
        return ''
    elif connection.last_token_aes.startswith(f'${ALGO_AES_CBC}$'):
        return reencrypt_cbc_to_ecb_mode(connection.last_token_aes, f'${ALGO_AES_CBC}$')
    else:
        return connection.last_token_aes


class Migration(migrations.Migration):

    dependencies = [
        ('motech', '0016_connectionsettings_include_client_id_and_more'),
    ]

    operations = [
        RunPython(migrate_api_settings, reverse_code=revert_api_settings),
    ]
