from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('userreports', '0016_change_primary_key_to_bigint'),
    ]

    operations = [
        # doc_id index covered by unique(doc_id)
        migrations.AlterField(
            model_name='asyncindicator',
            name='doc_id',
            field=models.CharField(max_length=255, unique=True),
        ),
        # doc_id index covered by unique(doc_id, indicator_config_id, validation_name
        migrations.AlterField(
            model_name='invaliducrdata',
            name='doc_id',
            field=models.CharField(max_length=255),
        ),
    ] + [
        migrations.RunSQL("DROP INDEX IF EXISTS {}".format(index), migrations.RunSQL.noop)
        for index in [
            'userreports_asyncindicator_doc_id_168418d8_like',
            'userreports_invaliducrdata_indicator_config_id_6d28eb7c_like',
            'userreports_asyncindicator_domain_10eda7e4_like',
            'userreports_invaliducrdata_domain_3890fc36_like',
        ]
    ]
