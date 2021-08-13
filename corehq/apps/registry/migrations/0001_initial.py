# Generated by Django 2.2.24 on 2021-07-27 08:01

import autoslug.fields
import corehq.apps.registry.models
from django.conf import settings
import django.contrib.postgres.fields
import django.contrib.postgres.fields.jsonb
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='DataRegistry',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('domain', models.CharField(max_length=255)),
                ('name', models.CharField(max_length=255)),
                ('slug', autoslug.fields.AutoSlugField(editable=False, populate_from='name', slugify=corehq.apps.registry.models.slugify_remove_stops, unique_with=('domain',))),
                ('description', models.TextField(blank=True)),
                ('is_active', models.BooleanField(default=True)),
                ('schema', django.contrib.postgres.fields.jsonb.JSONField(blank=True, null=True)),
                ('created_on', models.DateTimeField(auto_now_add=True)),
                ('modified_on', models.DateTimeField(auto_now=True)),
            ],
            options={
                'unique_together': {('domain', 'slug')},
            },
        ),
        migrations.CreateModel(
            name='RegistryGrant',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('from_domain', models.CharField(max_length=255)),
                ('to_domains', django.contrib.postgres.fields.ArrayField(base_field=models.CharField(max_length=255), size=None)),
                ('registry', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='grants', to='registry.DataRegistry')),
            ],
        ),
        migrations.CreateModel(
            name='RegistryAuditLog',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('action', models.CharField(choices=[('activated', 'Registry Activated'), ('deactivated', 'Registry De-activated'), ('invitation_added', 'Invitation Added'), ('invitation_removed', 'Invitation Revoked'), ('invitation_accepted', 'Invitation Accepted'), ('invitation_rejected', 'Invitation Rejected'), ('grant_added', 'Grant created'), ('grant_removed', 'Grant removed'), ('schema', 'Schema Changed'), ('data_accessed', 'Data Accessed')], max_length=32)),
                ('domain', models.CharField(db_index=True, max_length=255)),
                ('related_object_id', models.CharField(max_length=36)),
                ('related_object_type', models.CharField(choices=[('registry', 'Data Registry'), ('invitation', 'Invitation'), ('grant', 'Grant'), ('ucr', 'Report'), ('application', 'Case Search')], db_index=True, max_length=32)),
                ('detail', django.contrib.postgres.fields.jsonb.JSONField(null=True)),
                ('registry', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='audit_logs', to='registry.DataRegistry')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='registry_actions', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='RegistryPermission',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('domain', models.CharField(max_length=255)),
                ('read_only_group_id', models.CharField(max_length=255, null=True)),
                ('registry', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='permissions', to='registry.DataRegistry')),
            ],
            options={
                'unique_together': {('registry', 'domain')},
            },
        ),
        migrations.CreateModel(
            name='RegistryInvitation',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('domain', models.CharField(max_length=255)),
                ('created_on', models.DateTimeField(auto_now_add=True)),
                ('modified_on', models.DateTimeField(auto_now=True)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('accepted', 'Accepted'), ('rejected', 'Rejected')], default='pending', max_length=32)),
                ('registry', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='invitations', to='registry.DataRegistry')),
            ],
            options={
                'unique_together': {('registry', 'domain')},
            },
        ),
        migrations.AddIndex(
            model_name='registryauditlog',
            index=models.Index(fields=['domain'], name='registryauditlog_domain_idx'),
        ),
        migrations.AddIndex(
            model_name='registryauditlog',
            index=models.Index(fields=['action'], name='registryauditlog_action_idx'),
        ),
        migrations.AddIndex(
            model_name='registryauditlog',
            index=models.Index(fields=['related_object_type'], name='registryauditlog_rel_obj_idx'),
        ),
    ]
