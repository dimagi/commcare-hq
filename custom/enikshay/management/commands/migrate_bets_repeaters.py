from datetime import datetime
from django.core.management.base import BaseCommand
from corehq.util.log import with_progress_bar
from corehq.motech.repeaters.models import RepeatRecord
from corehq.motech.repeaters.dbaccessors import iter_repeat_records_by_domain, get_repeat_record_count
from custom.enikshay.integrations.bets import repeaters as bets_repeaters

DOMAIN = "enikshay"


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('--commit', action='store_true')

    def handle(self, **options):
        self.commit = options['commit']
        if self.commit:
            self.username = raw_input("Please enter the username\n")
            self.password = raw_input("Please enter the password\n")
        else:
            self.username, self.password = "", ""

        for repeater in self.get_repeaters():
            self.migrate_repeater(repeater)

        print "\nDone migrating all repeaters"

    def get_repeaters(self):
        return [
            bets_repeaters.ChemistBETSVoucherRepeater.get('ce5c88afa4dd86a53d7966dd3596ef30'),
            bets_repeaters.LabBETSVoucherRepeater.get('c1053ada294e88a9128aba078b5aab2a'),
            bets_repeaters.BETS180TreatmentRepeater.get('ce5c88afa4dd86a53d7966dd3596f3d6'),
            bets_repeaters.BETSDrugRefillRepeater.get('d0113e7507323484229dd4de23bbba78'),
            bets_repeaters.BETSSuccessfulTreatmentRepeater.get('d0113e7507323484229dd4de23bbba1b'),
            bets_repeaters.BETSDiagnosisAndNotificationRepeater.get('d0113e7507323484229dd4de23dca872'),
            bets_repeaters.BETSAYUSHReferralRepeater.get('2e2daa2c8e8c894d88e563d8fc6920a9'),
            # bets_repeaters.BETSBeneficiaryRepeater.get('ba001296f76894d629a63588ae041e21'),
            # not case repeaters
            # bets_repeaters.BETSLocationRepeater.get('ce5c88afa4dd86a53d7966dd350ca4c9'),
            # bets_repeaters.BETSUserRepeater.get('ba001296f76894d629a63588ae245336'),
        ]

    def migrate_repeater(self, old_repeater):
        new_repeater = old_repeater.__class__()
        print '\nCopying "{}"'.format(old_repeater.friendly_name)
        for prop in old_repeater.properties():
            if not prop.startswith('_') and not prop in ('password', 'username', 'url',):
                value = getattr(old_repeater, prop)
                print "    copying {} ({})".format(prop, type(value))
                setattr(new_repeater, prop, value)

        new_repeater.url = 'http://enikshay.myndgenie.in/Service/enikshay/bets/' + old_repeater.url.split('/')[-1]
        new_repeater.username = self.username
        new_repeater.password = self.password
        print new_repeater.__repr__()

        record_count = get_repeat_record_count(DOMAIN, repeater_id=old_repeater._id)
        print "Migrating {} records".format(record_count)

        if not self.commit:
            return

        new_repeater.save()

        already_sent = set()
        records = iter_repeat_records_by_domain(DOMAIN, repeater_id=old_repeater._id)
        for record in with_progress_bar(records, length=record_count):
            if not record.payload_id in already_sent:
                new_record = RepeatRecord(
                    domain=DOMAIN,
                    repeater_id=new_repeater._id,
                    repeater_type=new_repeater.doc_type,
                    payload_id=record.payload_id,
                    next_check=datetime.utcnow(),
                )
                new_record.save()
                already_sent.add(record.payload_id)
        print "Copied {} records (the rest were duplicates)".format(len(already_sent))
