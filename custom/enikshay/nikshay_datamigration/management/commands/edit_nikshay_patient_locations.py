from django.core.management import BaseCommand

from corehq.apps.locations.models import SQLLocation
from custom.enikshay.nikshay_datamigration.models import PatientDetail


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument(
            '--save',
            action='store_true',
            default=False,
        )

    def handle(self, domain, save=False, **options):
        for nikshay_id, location_owner_id in NIKSHAY_ID_TO_LOCATION_OWNER_ID.items():
            patient = PatientDetail.objects.get(PregId=nikshay_id)
            print 'Found patient %s' % patient.PregId
            location_owner = SQLLocation.active_objects.filter(
                domain=domain,
                location_id=location_owner_id,
            )
            print 'Found location_owner %s' % location_owner

            tu = location_owner.parent
            dto = tu.parent
            sto = dto.parent.parent

            phi_code = location_owner.metadata.get('nikshay_code')
            tu_code = tu.metadata.get('nikshay_code')
            dto_code = dto.metadata.get('nikshay_code')
            sto_code = sto.metadata.get('nikshay_code')

            patient.PHI = phi_code
            patient.Tbunitcode = tu_code
            patient.Dtocode = dto_code
            patient.scode = sto_code
            print 'Assigned %s to %s-%s-%d-%d' % (
                patient.PregId,
                patient.scode,
                patient.Dtocode,
                patient.Tbunitcode,
                patient.PHI,
            )

            if save:
                patient.save()
                print 'saved'
            else:
                print 'dry run, not saved'
            print '-------------'


NIKSHAY_ID_TO_LOCATION_OWNER_ID = {
    'GU-MSN-02-16-0050': 'e093b7e9224fcec6b458c4d32e4daaf7',
    'GU-MSN-02-16-0051': 'e093b7e9224fcec6b458c4d32e4daaf7',
    'GU-MSN-02-16-0052': 'e093b7e9224fcec6b458c4d32e4daaf7',
    'GU-MSN-02-16-0053': 'e093b7e9224fcec6b458c4d32e4daaf7',
    'GU-MSN-02-16-0079': 'e093b7e9224fcec6b458c4d32e4daaf7',
    'GU-MSN-02-16-0080': 'e093b7e9224fcec6b458c4d32e4daaf7',
    'GU-MSN-02-16-0113': 'e093b7e9224fcec6b458c4d32e4daaf7',
    'GU-MSN-02-16-0114': 'e093b7e9224fcec6b458c4d32e4daaf7',
    'GU-MSN-04-17-0022': 'e093b7e9224fcec6b458c4d32e4cf848',
    'GU-MSN-05-16-0121': 'e093b7e9224fcec6b458c4d32e4c5e9b',
    'GU-MSN-05-16-0122': 'e093b7e9224fcec6b458c4d32e4c5e9b',
    'GU-MSN-05-16-0123': 'e093b7e9224fcec6b458c4d32e4c5e9b',
    'GU-MSN-05-16-0247': 'e093b7e9224fcec6b458c4d32e4c5e9b',
    'GU-MSN-05-16-0270': 'e093b7e9224fcec6b458c4d32e4c905a',
    'MH-BAE-01-16-0139': 'e093b7e9224fcec6b458c4d32e4fa5df',
    'MH-BAE-01-16-0612': 'e093b7e9224fcec6b458c4d32e4f8e73',
    'MH-BAE-01-17-0060': 'e093b7e9224fcec6b458c4d32e4f8e73',
    'MH-BAE-01-17-0061': 'e093b7e9224fcec6b458c4d32e4f8e73',
    'MH-BAE-01-17-0065': 'e093b7e9224fcec6b458c4d32e4f8e73',
    'MH-BAE-01-17-0070': 'e093b7e9224fcec6b458c4d32e4f8e73',
    'MH-BAE-02-16-0047': 'e093b7e9224fcec6b458c4d32e4f7356',
    'MH-BAE-02-16-0048': 'e093b7e9224fcec6b458c4d32e4f7356',
    'MH-BAE-02-16-0059': 'e093b7e9224fcec6b458c4d32e4f6921',
    'MH-BAE-02-16-0060': 'e093b7e9224fcec6b458c4d32e4f6921',
    'MH-BAE-02-16-0061': 'e093b7e9224fcec6b458c4d32e4f6921',
    'MH-BAE-02-16-0062': 'e093b7e9224fcec6b458c4d32e4f6921',
    'MH-BAE-02-16-0063': 'e093b7e9224fcec6b458c4d32e4f6921',
    'MH-BAE-02-16-0064': 'e093b7e9224fcec6b458c4d32e4f6921',
    'MH-BAE-02-16-0065': 'e093b7e9224fcec6b458c4d32e4f6921',
    'MH-BAE-02-16-0066': 'e093b7e9224fcec6b458c4d32e4f6921',
    'MH-BAE-02-16-0125': 'e093b7e9224fcec6b458c4d32e4f6921',
    'MH-BAE-02-16-0126': 'e093b7e9224fcec6b458c4d32e4f6921',
    'MH-BAE-02-16-0127': 'e093b7e9224fcec6b458c4d32e4f6921',
    'MH-BAE-02-16-0128': 'e093b7e9224fcec6b458c4d32e4f6921',
    'MH-BAE-02-16-0129': 'e093b7e9224fcec6b458c4d32e4f6921',
    'MH-BAE-02-16-0130': 'e093b7e9224fcec6b458c4d32e4f6921',
    'MH-BAE-02-16-0131': 'e093b7e9224fcec6b458c4d32e4f6921',
    'MH-BAE-02-16-0132': 'e093b7e9224fcec6b458c4d32e4f6921',
    'MH-BAE-02-16-0133': 'e093b7e9224fcec6b458c4d32e4f6921',
    'MH-BAE-02-16-0134': 'e093b7e9224fcec6b458c4d32e4f6921',
    'MH-BAE-02-16-0135': 'e093b7e9224fcec6b458c4d32e4f6921',
    'MH-BAE-02-16-0136': 'e093b7e9224fcec6b458c4d32e4f6921',
    'MH-BAE-02-16-0137': 'e093b7e9224fcec6b458c4d32e4f6921',
    'MH-BAE-02-16-0138': 'e093b7e9224fcec6b458c4d32e4f6921',
    'MH-BAE-02-16-0139': 'e093b7e9224fcec6b458c4d32e4f6921',
    'MH-BAE-02-16-0140': 'e093b7e9224fcec6b458c4d32e4f6921',
    'MH-BAE-02-16-0141': 'e093b7e9224fcec6b458c4d32e4f6921',
    'MH-BAE-02-16-0142': 'e093b7e9224fcec6b458c4d32e4f6921',
    'MH-BAE-02-16-0143': 'e093b7e9224fcec6b458c4d32e4f6921',
    'MH-BAE-02-16-0144': 'e093b7e9224fcec6b458c4d32e4f6921',
    'MH-BAE-02-16-0145': 'e093b7e9224fcec6b458c4d32e4f6921',
    'MH-BAE-02-16-0146': 'e093b7e9224fcec6b458c4d32e4f6921',
    'MH-BAE-02-16-0147': 'e093b7e9224fcec6b458c4d32e4f6921',
    'MH-BAE-02-16-0148': 'e093b7e9224fcec6b458c4d32e4f6921',
    'MH-BAE-02-16-0149': 'e093b7e9224fcec6b458c4d32e4f6921',
    'MH-BAE-02-16-0197': 'e093b7e9224fcec6b458c4d32e4f6921',
    'MH-BAE-02-16-0198': 'e093b7e9224fcec6b458c4d32e4f6921',
    'MH-BAE-02-16-0199': 'e093b7e9224fcec6b458c4d32e4f6921',
    'MH-BAE-02-16-0200': 'e093b7e9224fcec6b458c4d32e4f6921',
    'MH-BAE-02-16-0201': 'e093b7e9224fcec6b458c4d32e4f6921',
    'MH-BAE-02-16-0202': 'e093b7e9224fcec6b458c4d32e4f6921',
    'MH-BAE-02-16-0203': 'e093b7e9224fcec6b458c4d32e4f6921',
    'MH-BAE-02-16-0204': 'e093b7e9224fcec6b458c4d32e4f6921',
    'MH-BAE-02-16-0205': 'e093b7e9224fcec6b458c4d32e4f6921',
    'MH-BAE-02-16-0206': 'e093b7e9224fcec6b458c4d32e4f6921',
    'MH-BAE-02-16-0207': 'e093b7e9224fcec6b458c4d32e4f6921',
    'MH-BAE-02-16-0362': 'e093b7e9224fcec6b458c4d32e4f7356',
    'MH-BAE-02-16-0506': 'e093b7e9224fcec6b458c4d32e4f5d09',
    'MH-BAE-02-16-0510': 'e093b7e9224fcec6b458c4d32e4f7356',
    'MH-BAE-02-17-0080': 'e093b7e9224fcec6b458c4d32e4f6921',
    'MH-BBR-01-16-0094': '1d110c46c3a20ae12e39031799a9219f',
    'MH-BBR-01-16-0201': '1d110c46c3a20ae12e39031799a92912',
    'MH-BBR-01-16-0202': '1d110c46c3a20ae12e39031799a92912',
    'MH-BBR-01-16-0203': '1d110c46c3a20ae12e39031799a92912',
    'MH-BBR-01-16-0204': '1d110c46c3a20ae12e39031799a92912',
    'MH-BBR-01-16-0312': '1d110c46c3a20ae12e39031799a9219f',
    'MH-BBR-01-16-0313': '1d110c46c3a20ae12e39031799a9219f',
    'MH-BBR-01-16-0432': '1d110c46c3a20ae12e39031799a912e3',
    'MH-BBR-01-17-0079': '1d110c46c3a20ae12e39031799a912e3',
    'MH-BBR-02-16-0156': '1d110c46c3a20ae12e39031799a9219f',
    'MH-KRL-01-16-0079': '1d110c46c3a20ae12e39031799a88dfe',
    'MH-KRL-01-16-0097': '1d110c46c3a20ae12e39031799a88dfe',
    'MH-KRL-01-16-0100': '1d110c46c3a20ae12e39031799a88dfe',
    'MH-KRL-01-16-0103': '1d110c46c3a20ae12e39031799a880e8',
    'MH-KRL-01-16-0104': '1d110c46c3a20ae12e39031799a880e8',
    'MH-KRL-01-16-0105': '1d110c46c3a20ae12e39031799a880e8',
    'MH-KRL-01-16-0106': '1d110c46c3a20ae12e39031799a880e8',
    'MH-KRL-01-16-0107': '1d110c46c3a20ae12e39031799a88dfe',
    'MH-KRL-01-16-0108': '1d110c46c3a20ae12e39031799a88dfe',
    'MH-KRL-01-16-0141': '1d110c46c3a20ae12e39031799a880e8',
    'MH-KRL-01-17-0142': '1d110c46c3a20ae12e39031799a88954',
    'MH-PRL-01-16-0149': 'e093b7e9224fcec6b458c4d32e4fe1bb',
    'MH-PRL-01-16-0150': 'e093b7e9224fcec6b458c4d32e4fe1bb',
    'MH-PRL-01-16-0259': 'e093b7e9224fcec6b458c4d32e509222',
}
