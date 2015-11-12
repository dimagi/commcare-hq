# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from corehq.apps.cleanup.pillow_migrations import noop_reverse_migration, migrate_legacy_pillows


def migrate_fluff_pillows(apps, schema_editor):
    fluff_pillow_names = [
        "CareBiharFluffPillow",
        "OpmUserFluffPillow",
        "UnicefMalawiFluffPillow",
        # "MalariaConsortiumFluffPillow",  # migrated in 0002
        "AncHmisCaseFluffPillow",
        "LdHmisCaseFluffPillow",
        "ImmunizationHmisCaseFluffPillow",
        "ProjectIndicatorsCaseFluffPillow",
        "McctMonthlyAggregateFormFluffPillow",
        "AllHmisCaseFluffPillow",
        "CouvertureFluffPillow",
        "TauxDeSatisfactionFluffPillow",
        "IntraHealthFluffPillow",
        "RecapPassageFluffPillow",
        "TauxDeRuptureFluffPillow",
        "LivraisonFluffPillow",
        "RecouvrementFluffPillow",
        "GeographyFluffPillow",
        "FarmerRecordFluffPillow",
        "WorldVisionMotherFluffPillow",
        "WorldVisionChildFluffPillow",
        "WorldVisionHierarchyFluffPillow",
        "UCLAPatientFluffPillow",
    ]
    migrate_legacy_pillows(apps, fluff_pillow_names)


class Migration(migrations.Migration):

    dependencies = [
        ('cleanup', '0002_convert_mc_checkpoint_to_sql'),
    ]

    operations = [
        migrations.RunPython(migrate_fluff_pillows, noop_reverse_migration)
    ]
