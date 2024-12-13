# Generated by Django 4.2.16 on 2024-11-18 19:52

from django.db import migrations, models
from django.db.models import Q
from corehq.motech.utils import b64_aes_cbc_encrypt
from corehq.sql_db.util import paginate_query
from corehq.util.django_migrations import skip_on_fresh_install

from dimagi.utils.chunked import chunked


@skip_on_fresh_install
def copy_key_to_hashed_key(apps, schema_editor):
    db_alias = schema_editor.connection.alias
    HQApiKey = apps.get_model('users', 'HQApiKey')

    for batch in _batch_query(db_alias, HQApiKey, Q(), 500):
        for api_key in batch:
            if not api_key.encrypted_key:
                api_key.encrypted_key = b64_aes_cbc_encrypt(api_key.key)
        HQApiKey.objects.bulk_update(batch, ["encrypted_key"])


def _batch_query(db_alias, model, query, batch_size):
    it = paginate_query(db_alias, model, query, query_size=batch_size)
    return chunked(it, batch_size)


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0074_alter_sqluserdata_profile'),
    ]

    operations = [
        migrations.AddField(
            model_name='hqapikey',
            name='encrypted_key',
            field=models.CharField(blank=True, db_index=True, default='', max_length=128),
        ),
        migrations.RunPython(copy_key_to_hashed_key, migrations.RunPython.noop),
    ]