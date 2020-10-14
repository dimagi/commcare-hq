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
                    ('CANCELLED', 'Cancelled')
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
                'ordering': ['created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='sqlrepeaterstub',
            index=models.Index(fields=['domain', 'couch_id'],
                               name='repeaters_s_domain_454f6d_idx'),
        ),
        migrations.AddIndex(
            model_name='sqlrepeatrecord',
            index=models.Index(fields=['domain'],
                               name='repeaters_s_domain_b82273_idx'),
        ),
        migrations.AddIndex(
            model_name='sqlrepeatrecord',
            index=models.Index(fields=['couch_id'],
                               name='repeaters_s_couch_i_75ba4d_idx'),
        ),
        migrations.AddIndex(
            model_name='sqlrepeatrecord',
            index=models.Index(fields=['payload_id'],
                               name='repeaters_s_payload_e42bfa_idx'),
        ),
        migrations.AddIndex(
            model_name='sqlrepeatrecord',
            index=models.Index(fields=['registered_at'],
                               name='repeaters_s_registe_a21901_idx'),
        ),
    ]
