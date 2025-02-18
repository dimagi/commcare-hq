# Generated by Django 4.2.18 on 2025-02-17 12:46

from django.conf import settings
import django.contrib.postgres.fields
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='BulkEditSession',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('domain', models.CharField(db_index=True, max_length=255)),
                ('created_on', models.DateTimeField(auto_now_add=True)),
                ('last_modified', models.DateTimeField(auto_now=True)),
                ('session_id', models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True)),
                ('session_type', models.CharField(choices=[('case', 'Case'), ('form', 'Form')], max_length=4)),
                ('identifier', models.CharField(db_index=True, max_length=255)),
                ('committed_on', models.DateTimeField(blank=True, null=True)),
                ('task_id', models.UUIDField(blank=True, db_index=True, null=True, unique=True)),
                ('result', models.JSONField(blank=True, null=True)),
                ('completed_on', models.DateTimeField(blank=True, null=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='bulk_edit_sessions', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='BulkEditRecord',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('doc_id', models.CharField(db_index=True, max_length=126, unique=True)),
                ('is_selected', models.BooleanField(default=True)),
                ('calculated_change_id', models.UUIDField(blank=True, null=True)),
                ('calculated_properties', models.JSONField(blank=True, null=True)),
                ('session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='records', to='data_cleaning.bulkeditsession')),
            ],
        ),
        migrations.CreateModel(
            name='BulkEditPinnedFilter',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('index', models.IntegerField(default=0)),
                ('filter_type', models.CharField(choices=[('case_owners', 'case_owners'), ('case_status', 'case_status')], max_length=11)),
                ('value', django.contrib.postgres.fields.ArrayField(base_field=models.TextField(), blank=True, null=True, size=None)),
                ('session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pinned_filters', to='data_cleaning.bulkeditsession')),
            ],
        ),
        migrations.CreateModel(
            name='BulkEditColumnFilter',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('index', models.IntegerField(default=0)),
                ('property', models.CharField(max_length=255)),
                ('data_type', models.CharField(choices=[('text', 'Text'), ('integer', 'Integer'), ('phone_number', 'Phone Number or Numeric ID'), ('decimal', 'Decimal'), ('date', 'Date'), ('time', 'Time'), ('datetime', 'Date and Time'), ('single_option', 'Single Option'), ('multiple_option', 'Multiple Option'), ('gps', 'GPS'), ('barcode', 'Barcode'), ('password', 'Password')], default='text', max_length=15)),
                ('match_type', models.CharField(choices=[('exact', 'exact'), ('is_not', 'is_not'), ('starts', 'starts'), ('ends', 'ends'), ('is_empty', 'is_empty'), ('is_not_empty', 'is_not_empty'), ('is_null', 'is_null'), ('is_not_null', 'is_not_null'), ('fuzzy', 'fuzzy'), ('not_fuzzy', 'not_fuzzy'), ('phonetic', 'phonetic'), ('not_phonetic', 'not_phonetic'), ('lt', 'lt'), ('gt', 'gt'), ('is_any', 'is_any'), ('is_not_any', 'is_not_any'), ('is_all', 'is_all'), ('is_not_all', 'is_not_all')], default='exact', max_length=12)),
                ('value', models.TextField(blank=True, null=True)),
                ('session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='column_filters', to='data_cleaning.bulkeditsession')),
            ],
        ),
        migrations.CreateModel(
            name='BulkEditColumn',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('index', models.IntegerField(default=0)),
                ('property', models.CharField(max_length=255)),
                ('label', models.CharField(max_length=255)),
                ('data_type', models.CharField(choices=[('text', 'Text'), ('integer', 'Integer'), ('phone_number', 'Phone Number or Numeric ID'), ('decimal', 'Decimal'), ('date', 'Date'), ('time', 'Time'), ('datetime', 'Date and Time'), ('single_option', 'Single Option'), ('multiple_option', 'Multiple Option'), ('gps', 'GPS'), ('barcode', 'Barcode'), ('password', 'Password')], default='text', max_length=15)),
                ('is_system', models.BooleanField(default=False)),
                ('session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='columns', to='data_cleaning.bulkeditsession')),
            ],
        ),
        migrations.CreateModel(
            name='BulkEditChange',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('change_id', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('created_on', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('property', models.CharField(max_length=255)),
                ('action_type', models.CharField(choices=[('replace', 'Replace'), ('find_replace', 'Find & Replace'), ('copy_replace', 'Copy & Replace'), ('strip', 'Strip Whitespaces'), ('title_case', 'Make Title Case'), ('upper_case', 'Make Upper Case'), ('lower_case', 'Make Lower Case'), ('make_empty', 'Make Value Empty'), ('make_null', 'Make Value NULL'), ('reset', 'Undo All Edits')], max_length=12)),
                ('find_string', models.TextField(blank=True, null=True)),
                ('replace_string', models.TextField(blank=True, null=True)),
                ('use_regex', models.BooleanField(default=False)),
                ('replace_all_string', models.TextField(blank=True, null=True)),
                ('copy_from_property', models.CharField(max_length=255)),
                ('records', models.ManyToManyField(related_name='changes', to='data_cleaning.bulkeditrecord')),
                ('session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='changes', to='data_cleaning.bulkeditsession')),
            ],
            options={
                'ordering': ['created_on'],
            },
        ),
    ]
