from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('repeaters', '0001_adjust_auth_field_format'),
    ]

    operations = [
        migrations.CreateModel(
            name='SQLRepeaterStub',
            fields=[
                ('id', models.AutoField(auto_created=True,
                                        primary_key=True,
                                        serialize=False,
                                        verbose_name='ID')),
                ('domain', models.CharField(max_length=126)),
                ('couch_id', models.CharField(max_length=36)),
                ('is_paused', models.BooleanField(default=False)),
                ('next_attempt_at', models.DateTimeField(blank=True,
                                                         null=True)),
                ('last_attempt_at', models.DateTimeField(blank=True,
                                                         null=True)),
            ],
            options={
                'db_table': 'repeaters_repeaterstub',
            },
        ),
        migrations.CreateModel(
            name='SQLRepeatRecord',
            fields=[
                ('id', models.AutoField(auto_created=True,
                                        primary_key=True,
                                        serialize=False,
                                        verbose_name='ID')),
                ('domain', models.CharField(max_length=126)),
                ('couch_id', models.CharField(blank=True, max_length=36,
                                              null=True)),
                ('payload_id', models.CharField(max_length=36)),
                ('state', models.TextField(
                    choices=[
                        ('PENDING', 'Pending'),
                        ('SUCCESS', 'Succeeded'),
                        ('FAIL', 'Failed'),
                        ('CANCELLED', 'Cancelled'),
                    ],
                    default='PENDING',
                )),
                ('registered_at', models.DateTimeField()),
                ('repeater', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='repeat_records',
                    to='repeaters.SQLRepeaterStub',
                )),
            ],
            options={
                'db_table': 'repeaters_repeatrecord',
                'ordering': ['registered_at'],
            },
        ),
        migrations.CreateModel(
            name='SQLRepeatRecordAttempt',
            fields=[
                ('id', models.AutoField(auto_created=True,
                                        primary_key=True,
                                        serialize=False,
                                        verbose_name='ID')),
                ('state', models.TextField(choices=[
                    ('PENDING', 'Pending'),
                    ('SUCCESS', 'Succeeded'),
                    ('FAIL', 'Failed'),
                    ('CANCELLED', 'Cancelled'),
                ])),
                ('message', models.TextField(blank=True, null=True)),
                ('traceback', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(
                    default=django.utils.timezone.now)),
                ('repeat_record', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='repeaters.SQLRepeatRecord',
                )),
            ],
            options={
                'db_table': 'repeaters_repeatrecordattempt',
                'ordering': ['created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='sqlrepeaterstub',
            index=models.Index(fields=['domain'],
                               name='repeaters_r_domain_23d304_idx'),
        ),
        migrations.AddIndex(
            model_name='sqlrepeaterstub',
            index=models.Index(fields=['couch_id'],
                               name='repeaters_r_couch_i_a2d469_idx'),
        ),
        migrations.AddIndex(
            model_name='sqlrepeatrecord',
            index=models.Index(fields=['domain'],
                               name='repeaters_r_domain_3ae9ab_idx'),
        ),
        migrations.AddIndex(
            model_name='sqlrepeatrecord',
            index=models.Index(fields=['couch_id'],
                               name='repeaters_r_couch_i_ea5782_idx'),
        ),
        migrations.AddIndex(
            model_name='sqlrepeatrecord',
            index=models.Index(fields=['payload_id'],
                               name='repeaters_r_payload_f64556_idx'),
        ),
        migrations.AddIndex(
            model_name='sqlrepeatrecord',
            index=models.Index(fields=['registered_at'],
                               name='repeaters_r_registe_b48c68_idx'),
        ),
    ]
