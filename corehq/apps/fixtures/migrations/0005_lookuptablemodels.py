import corehq.sql_db.fields
import dimagi.utils.couch.migration
from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('fixtures', '0004_userlookuptablestatus'),
    ]

    operations = [
        migrations.CreateModel(
            name='LookupTable',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ('domain', corehq.sql_db.fields.CharIdField(db_index=True, default=None, max_length=126)),
                ('is_global', models.BooleanField(default=False)),
                ('tag', corehq.sql_db.fields.CharIdField(default=None, max_length=32)),
                ('fields', models.JSONField(default=list)),
                ('item_attributes', models.JSONField(default=list)),
                ('description', models.CharField(default='', max_length=255)),
            ],
            options={
                'unique_together': {('domain', 'tag')},
            },
            bases=(dimagi.utils.couch.migration.SyncSQLToCouchMixin, models.Model),
        ),
    ]
