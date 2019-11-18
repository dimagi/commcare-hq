from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('pillowtop', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='djangopillowcheckpoint',
            name='sequence_format',
            field=models.CharField(default=b'text', max_length=20, choices=[(b'text', b'text'), (b'json', b'json')]),
            preserve_default=True,
        ),
    ]
