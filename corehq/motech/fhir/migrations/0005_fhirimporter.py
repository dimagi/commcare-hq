from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('motech', '0008_requestlog_response_headers'),
        ('fhir', '0004_remove_fhirresourcetype_template'),
    ]

    operations = [
        migrations.CreateModel(
            name='FHIRImporter',
            fields=[
                ('id', models.AutoField(
                    auto_created=True,
                    primary_key=True,
                    serialize=False,
                    verbose_name='ID',
                )),
                ('domain', models.CharField(db_index=True, max_length=127)),
                ('fhir_version', models.CharField(
                    choices=[('4.0.1', 'R4')],
                    default='4.0.1',
                    max_length=12,
                )),
                ('frequency', models.CharField(
                    choices=[('daily', 'Daily')],
                    default='daily',
                    max_length=12,
                )),
                ('owner_id', models.CharField(max_length=32)),
                ('connection_settings', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    to='motech.ConnectionSettings',
                )),
            ],
        ),
        migrations.AddIndex(
            model_name='fhirimporter',
            index=models.Index(
                fields=['domain'],
                name='fhir_fhirim_domain_41a7dc_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='fhirimporter',
            index=models.Index(
                fields=['frequency'],
                name='fhir_fhirim_frequen_dd0d53_idx',
            ),
        ),
    ]
