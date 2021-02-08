from django.db import migrations

from couchdbkit import ResourceNotFound

from corehq.motech.repeaters.models import Repeater

DELETED_REPEATER_CLASSES = (
    'ChemistBETSVoucherRepeater',
    'LabBETSVoucherRepeater',
    'BETS180TreatmentRepeater',
    'BETSDrugRefillRepeater',
    'BETSSuccessfulTreatmentRepeater',
    'BETSDiagnosisAndNotificationRepeater',
    'BETSAYUSHReferralRepeater',
    'BETSUserRepeater',
    'BETSLocationRepeater',
    'BETSBeneficiaryRepeater',

    'NikshayRegisterPatientRepeater',
    'NikshayHIVTestRepeater',
    'NikshayTreatmentOutcomeRepeater',
    'NikshayFollowupRepeater',
    'NikshayRegisterPrivatePatientRepeater',
    'NikshayHealthEstablishmentRepeater',

    'NinetyNineDotsRegisterPatientRepeater',
    'NinetyNineDotsUpdatePatientRepeater',
    'NinetyNineDotsAdherenceRepeater',
    'NinetyNineDotsTreatmentOutcomeRepeater',
    'NinetyNineDotsUnenrollPatientRepeater',
)


def _migrate_to_connectionsettings(apps, schema_editor):
    for repeater in iter_repeaters():
        if not repeater.connection_settings_id:
            repeater.create_connection_settings()


def iter_repeaters():
    for result in Repeater.get_db().view('repeaters/repeaters',
                                         reduce=False,
                                         include_docs=True).all():
        try:
            repeater = Repeater.wrap(result['doc'])
        except ResourceNotFound:
            if result['doc']['doc_type'] in DELETED_REPEATER_CLASSES:
                # repeater is an instance of a class that has been deleted
                # from the codebase. It is safe to delete because it does
                # not have repeat records waiting to be sent, and no future
                # repeat records will be created for it.
                delete_zombie_repeater_instance(result['doc'])
                continue
            else:
                raise
        else:
            yield repeater


def delete_zombie_repeater_instance(document: dict):
    assert document['doc_type'] in DELETED_REPEATER_CLASSES
    db = Repeater.get_db()
    # Do not delete old repeat records. There could be thousands, and they
    # are benign because they will not be resent.
    db.delete_doc(document['_id'])


class Migration(migrations.Migration):

    dependencies = [
        ('repeaters', '0002_sqlrepeatrecord'),
        ('motech', '0007_auto_20200909_2138'),
    ]

    operations = [
        migrations.RunPython(_migrate_to_connectionsettings,
                             reverse_code=migrations.RunPython.noop,
                             elidable=True),
    ]
