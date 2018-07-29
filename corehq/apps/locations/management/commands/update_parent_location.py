from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
from django.core.management.base import BaseCommand, CommandError
from corehq.apps.locations.models import SQLLocation


class Command(BaseCommand):
    help = ("This command is intended to be used for updating the parent "
            "location of a location that has child locations. Before using "
            "this script you should make sure this operation is ok to do "
            "given your use case.")

    @staticmethod
    def get_location(location_id):
        location = SQLLocation.by_location_id(location_id)

        if not location:
            raise CommandError("Could not find location %s" % location_id)

        return location

    def validate_locations(self, loc_to_update, new_parent_loc):
        if loc_to_update.domain != new_parent_loc.domain:
            raise CommandError("Locations must be belong to the same domain")

        if loc_to_update.is_archived or new_parent_loc.is_archived:
            raise CommandError("Locations must not be archived")

        if loc_to_update.location_type.parent_type != new_parent_loc.location_type:
            raise CommandError("Location types do not match up")

        return (loc_to_update, new_parent_loc)

    def add_arguments(self, parser):
        parser.add_argument(
            'loc_to_update',
            type=self.get_location,
        )
        parser.add_argument(
            'new_parent_loc',
            type=self.get_location,
        )

    def handle(self, loc_to_update, new_parent_loc, **options):
        print('Validating locations...')
        loc_to_update, new_parent_loc = self.validate_locations(loc_to_update, new_parent_loc)
        print('done')

        print('Updating new parent...')
        loc_to_update.parent = new_parent_loc
        loc_to_update.save()
        print('done')

        print('Updating lineage for all couch locations...')
        for descendant in loc_to_update.get_descendants(include_self=False):
            # We have to do this to sync the lineage to the couch Location
            descendant.save()
        print('done')

        print('Double-checking location types...')
        for descendant in loc_to_update.get_descendants(include_self=True):
            if descendant.location_type.parent_type != descendant.parent.location_type:
                print('Mismatch found in location type hierarchy for location %s' % descendant.location_id)
        print('done')
