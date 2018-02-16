# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='PatientDetail',
            fields=[
                ('PregId', models.CharField(max_length=255, serialize=False, primary_key=True)),
                ('scode', models.CharField(max_length=255, null=True)),
                ('Dtocode', models.CharField(max_length=255, null=True)),
                ('Tbunitcode', models.IntegerField()),
                ('pname', models.CharField(max_length=255)),
                ('pgender', models.CharField(max_length=255, choices=[(b'F', b'F'), (b'M', b'M'), (b'T', b'T')])),
                ('page', models.CharField(max_length=255)),
                ('poccupation', models.CharField(max_length=255)),
                ('paadharno', models.BigIntegerField(null=True)),
                ('paddress', models.CharField(max_length=255)),
                ('pmob', models.CharField(max_length=255, null=True)),
                ('plandline', models.CharField(max_length=255, null=True)),
                ('ptbyr', models.CharField(max_length=255, null=True)),
                ('cname', models.CharField(max_length=255, null=True)),
                ('caddress', models.CharField(max_length=255, null=True)),
                ('cmob', models.CharField(max_length=255, null=True)),
                ('clandline', models.CharField(max_length=255, null=True)),
                ('cvisitedby', models.CharField(max_length=255, null=True)),
                ('dcpulmunory', models.CharField(max_length=255, choices=[(b'y', b'y'), (b'Y', b'Y'), (b'N', b'N'), (b'P', b'P')])),
                ('dcexpulmunory', models.CharField(max_length=255)),
                ('dcpulmunorydet', models.CharField(max_length=255, null=True)),
                ('dotname', models.CharField(max_length=255, null=True)),
                ('dotdesignation', models.CharField(max_length=255, null=True)),
                ('dotmob', models.CharField(max_length=255, null=True)),
                ('dotlandline', models.CharField(max_length=255, null=True)),
                ('dotpType', models.CharField(max_length=255)),
                ('dotcenter', models.CharField(max_length=255, null=True)),
                ('PHI', models.IntegerField()),
                ('dotmoname', models.CharField(max_length=255, null=True)),
                ('dotmosdone', models.CharField(max_length=255)),
                ('atbtreatment', models.CharField(max_length=255, null=True, choices=[(b'Y', b'Y'), (b'N', b'N')])),
                ('atbduration', models.CharField(max_length=255, null=True)),
                ('atbsource', models.CharField(max_length=255, null=True, choices=[(b'G', b'G'), (b'N', b'N'), (b'O', b'O'), (b'P', b'P')])),
                ('atbregimen', models.CharField(max_length=255, null=True)),
                ('atbyr', models.CharField(max_length=255, null=True)),
                ('Ptype', models.CharField(max_length=255)),
                ('pcategory', models.CharField(max_length=255)),
                ('regBy', models.CharField(max_length=255)),
                ('regDate', models.CharField(max_length=255)),
                ('isRntcp', models.CharField(max_length=255)),
                ('dotprovider_id', models.CharField(max_length=255)),
                ('pregdate1', models.DateField()),
                ('cvisitedDate1', models.CharField(max_length=255)),
                ('InitiationDate1', models.CharField(max_length=255)),
                ('dotmosignDate1', models.CharField(max_length=255)),
            ],
        ),
        migrations.CreateModel(
            name='Followup',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True)),
                ('PatientID', models.ForeignKey(to='nikshay_datamigration.PatientDetail', on_delete=models.CASCADE)),
                ('IntervalId', models.CharField(max_length=255)),
                ('TestDate', models.CharField(max_length=255, null=True)),
                ('DMC', models.CharField(max_length=255)),
                ('LabNo', models.CharField(max_length=255, null=True)),
                ('SmearResult', models.CharField(max_length=255)),
                ('PatientWeight', models.CharField(max_length=255)),
                ('DmcStoCode', models.CharField(max_length=255)),
                ('DmcDtoCode', models.CharField(max_length=255)),
                ('DmcTbuCode', models.CharField(max_length=255)),
                ('RegBy', models.CharField(max_length=255)),
                ('regdate', models.CharField(max_length=255)),
            ],
        ),
        migrations.CreateModel(
            name='Outcome',
            fields=[
                ('PatientId', models.OneToOneField(primary_key=True, serialize=False, to='nikshay_datamigration.PatientDetail', on_delete=models.CASCADE)),
                ('Outcome', models.CharField(max_length=255)),
                ('OutcomeDate', models.CharField(max_length=255, null=True)),
                ('MO', models.CharField(max_length=255, null=True)),
                ('XrayEPTests', models.CharField(max_length=255)),
                ('MORemark', models.CharField(max_length=255, null=True)),
                ('HIVStatus', models.CharField(max_length=255, null=True)),
                ('HIVTestDate', models.CharField(max_length=255, null=True)),
                ('CPTDeliverDate', models.CharField(max_length=255, null=True)),
                ('ARTCentreDate', models.CharField(max_length=255, null=True)),
                ('InitiatedOnART', models.CharField(max_length=255, null=True)),
                ('InitiatedDate', models.CharField(max_length=255, null=True)),
                ('userName', models.CharField(max_length=255)),
                ('loginDate', models.CharField(max_length=255)),
                ('OutcomeDate1', models.CharField(max_length=255)),
            ],
        ),
    ]
