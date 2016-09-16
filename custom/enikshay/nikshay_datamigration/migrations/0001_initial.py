# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Followup',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('PatientID', models.CharField(max_length=255, null=True)),
                ('IntervalId', models.CharField(max_length=255, null=True)),
                ('TestDate', models.CharField(max_length=255, null=True)),
                ('DMC', models.CharField(max_length=255, null=True)),
                ('LabNo', models.CharField(max_length=255, null=True)),
                ('SmearResult', models.CharField(max_length=255, null=True)),
                ('PatientWeight', models.CharField(max_length=255, null=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Household',
            fields=[
                ('id', models.IntegerField(serialize=False, primary_key=True)),
                ('PatientID', models.CharField(max_length=255, null=True)),
                ('Name', models.CharField(max_length=255, null=True)),
                ('Dosage', models.CharField(max_length=255, null=True)),
                ('Weight', models.CharField(max_length=255, null=True)),
                ('M1', models.CharField(max_length=255, null=True)),
                ('M2', models.CharField(max_length=255, null=True)),
                ('M3', models.CharField(max_length=255, null=True)),
                ('M4', models.CharField(max_length=255, null=True)),
                ('M5', models.CharField(max_length=255, null=True)),
                ('M6', models.CharField(max_length=255, null=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='PatientDetail',
            fields=[
                ('PregId', models.CharField(max_length=255, serialize=False, primary_key=True)),
                ('Stocode', models.CharField(max_length=255, null=True)),
                ('Dtocode', models.CharField(max_length=255, null=True)),
                ('Tbunitcode', models.IntegerField(null=True)),
                ('pname', models.CharField(max_length=255, null=True)),
                ('pgender', models.CharField(max_length=255)),
                ('page', models.IntegerField(null=True)),
                ('poccupation', models.IntegerField(null=True)),
                ('paadharno', models.CharField(max_length=255, null=True)),
                ('paddress', models.CharField(max_length=255, null=True)),
                ('pmob', models.CharField(max_length=255, null=True)),
                ('plandline', models.BigIntegerField(null=True)),
                ('ptbyr', models.CharField(max_length=255, null=True)),
                ('pregdate1', models.DateField()),
                ('cname', models.CharField(max_length=255, null=True)),
                ('caddress', models.CharField(max_length=255, null=True)),
                ('cmob', models.CharField(max_length=255, null=True)),
                ('clandline', models.BigIntegerField(null=True)),
                ('cvisitedby', models.CharField(max_length=255, null=True)),
                ('cvisitedDate1', models.CharField(max_length=255, null=True)),
                ('dcpulmunory', models.CharField(max_length=255, choices=[(b'y', b'y'), (b'N', b'N')])),
                ('dcexpulmunory', models.CharField(max_length=255, null=True)),
                ('dcpulmunorydet', models.CharField(max_length=255, null=True)),
                ('dotname', models.CharField(max_length=255, null=True)),
                ('dotdesignation', models.CharField(max_length=255, null=True)),
                ('dotmob', models.CharField(max_length=255, null=True)),
                ('dotlandline', models.CharField(max_length=255, null=True)),
                ('dotpType', models.IntegerField()),
                ('dotcenter', models.CharField(max_length=255, null=True)),
                ('PHI', models.IntegerField()),
                ('dotmoname', models.CharField(max_length=255, null=True)),
                ('dotmosignDate', models.CharField(max_length=255, null=True)),
                ('atbtreatment', models.CharField(max_length=255, choices=[(b'Y', b'Y'), (b'N', b'N')])),
                ('atbduration', models.CharField(max_length=255, null=True)),
                ('atbsource', models.CharField(max_length=255, null=True, choices=[(b'G', b'G'), (b'O', b'O'), (b'P', b'P')])),
                ('atbregimen', models.CharField(max_length=255, null=True)),
                ('atbyr', models.IntegerField(null=True)),
                ('Ptype', models.IntegerField()),
                ('pcategory', models.IntegerField()),
                ('InitiationDate1', models.CharField(max_length=255, null=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Outcome',
            fields=[
                ('PatientId', models.ForeignKey(primary_key=True, serialize=False, to='nikshay_datamigration.PatientDetail')),
                ('Outcome', models.CharField(max_length=255, null=True)),
                ('OutcomeDate1', models.CharField(max_length=255, null=True)),
                ('MO', models.CharField(max_length=255, null=True)),
                ('XrayEPTests', models.CharField(max_length=255, null=True)),
                ('MORemark', models.CharField(max_length=255, null=True)),
                ('HIVStatus', models.CharField(max_length=255, null=True)),
                ('HIVTestDate', models.CharField(max_length=255, null=True)),
                ('CPTDeliverDate', models.CharField(max_length=255, null=True)),
                ('ARTCentreDate', models.CharField(max_length=255, null=True)),
                ('InitiatedOnART', models.CharField(max_length=255, null=True)),
                ('InitiatedDate', models.CharField(max_length=255, null=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
