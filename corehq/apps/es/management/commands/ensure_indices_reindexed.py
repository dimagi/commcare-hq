from django.core.management.base import BaseCommand, CommandError

from corehq.apps.es import CANONICAL_NAME_ADAPTER_MAP, const
from corehq.apps.es.client import manager
from corehq.apps.es.transient_util import doc_adapter_from_cname

helptext = """
The management command is intended for execution during Django migrations and is designed for use
in Elasticsearch upgrades. Its purpose is to ensure the reindexing of all Elasticsearch indexes.
The command accomplishes this by comparing the document counts in both primary and secondary indexes for each app.
If the difference in count is not zero for indexes or exceeds 1% for high-frequency indices such as
case-search, cases, and forms, the command will fail.
However, it will skip execution if the current Elasticsearch version is greater than the specified version
which means that Elasticsearch is already upgraded.
"""


class Command(BaseCommand):

    help = helptext

    REASONABLE_DIFF_PERCENT = 1

    def add_arguments(self, parser):
        parser.add_argument(
            'current_es_version', type=int, choices=[2, 5],
            help="""A valid ES major version from which the data is being migrated from
            For eg - If you are upgrading from 2 to 5 the current_es_version should be 2
            """
        )

        parser.add_argument('changelog', help="Changelog entry for the upgrade that outlines reindex steps")

    def handle(self, current_es_version, changelog, **kwargs):
        if manager.elastic_major_version != current_es_version:
            print(f"""
                Skipping Reindex verify checks!
                Environment's ElasticSearch version is {manager.elastic_major_version}
            """)
            return
        if not self.check_indices_are_consistent():
            raise CommandError(
                """
                Your elasticsearch indices seem to be in inconsistent state.
                You must fix the inconsitencies before you can deploy
                """
            )

        missing_primary, missing_secondary = self._return_missing_index_names()
        if missing_primary and not missing_secondary:
            # User has confirmed that they have followed manual reindex. So we can ignore the further checks
            return

        inconsistent_doc_count = []
        for index_cname in CANONICAL_NAME_ADAPTER_MAP.keys():
            if not self.is_doc_count_difference_reasonable(index_cname):
                inconsistent_doc_count.append(index_cname)

        if inconsistent_doc_count:
            raise CommandError(
                f"""
                Data is not properly reindexed in your indices. See above logs.
                Please go through the changelog {changelog} and make sure you have properly followed it.
                You can't deploy until you have fixed the discrepancies"""
            )

    @classmethod
    def check_indices_are_consistent(cls):
        """
        Returns ``False`` if any of the following conditions are true-
            - If there are any missing primary indices,
            and user confirms that they have not followed manual reindex process
            - If there are missing secondary indices
        """
        missing_primary, missing_secondary = cls._return_missing_index_names()
        if not missing_primary and not missing_secondary:
            return True
        elif missing_primary and not missing_secondary:
            user_input = input(
                f"""We've identified that certain old indices are absent from your CommCare setup.
                Missing Indices: {missing_primary}

                Can you confirm whether a custom reindexing approach has been implemented? -

                Press 'y' or 'Y' to confirm. Press any other key to abort!
            """)

            if user_input.lower() == 'y':
                return True

        elif missing_secondary:
            # Highly unlikely event, adding for some additional safety
            print(
                f"""
                Error: Your Commcare Instance does not seem to be in a consistent state.
                We found some required indices {missing_secondary} missing from your installation.
                Please reach out to us on https://forum.dimagi.com/"""
            )
            return False

        return False

    @classmethod
    def _return_missing_index_names(cls):
        """
        Returns a tuple of missing primary and secondary index names
        """
        missing_primary = []
        missing_secondary = []
        for cname in CANONICAL_NAME_ADAPTER_MAP.keys():
            primary_adapter, secondary_adapter = cls.get_both_adapters_for_cname(cname)
            if not manager.index_exists(primary_adapter.index_name):
                missing_primary.append(primary_adapter.index_name)
            if not manager.index_exists(secondary_adapter.index_name):
                missing_secondary.append(secondary_adapter.index_name)
        return missing_primary, missing_secondary

    def is_doc_count_difference_reasonable(self, cname):
        # We will accept delta of 1% in doc count difference
        high_frequency_indices = {'case_search', 'cases', 'forms'}
        primary_adapter, secondary_adapter = self.get_both_adapters_for_cname(cname)
        delta_perc = self.get_doc_count_delta_percent(cname)
        return delta_perc == 0 or (
            primary_adapter.canonical_name in high_frequency_indices
            and delta_perc <= self.REASONABLE_DIFF_PERCENT
        )

    @classmethod
    def _primary_index_name(cls, cname):
        return getattr(const, f'HQ_{cname.upper()}_INDEX_NAME')

    @classmethod
    def _secondary_index_name(cls, cname):
        return getattr(const, f'HQ_{cname.upper()}_SECONDARY_INDEX_NAME')

    @classmethod
    def get_both_adapters_for_cname(cls, cname):

        """
        returns instance of primary and secondary adapter for the instance
        """
        adapter = doc_adapter_from_cname(cname)
        primary_index_name = cls._primary_index_name(cname)
        secondary_index_name = cls._secondary_index_name(cname)

        primary_adapter = type(adapter)(primary_index_name, adapter.type)
        secondary_adapter = type(adapter)(secondary_index_name, adapter.type)

        return (primary_adapter, secondary_adapter)

    def get_doc_count_delta_percent(self, cname):
        """
        For the given cname the function returns the difference in count of primary and secondary indices
        """
        primary_adapter, secondary_adapter = self.get_both_adapters_for_cname(cname)
        primary_adapter.delete_tombstones()
        secondary_adapter.delete_tombstones()

        primary_count = primary_adapter.count({})
        secondary_count = secondary_adapter.count({})

        print(f"\nDoc Count in old Index {primary_adapter.index_name}: {primary_count}")
        print(f"\nDoc Count in new Index {secondary_adapter.index_name}: {secondary_count}")

        diff = abs(primary_count - secondary_count)
        delta = (diff / primary_count) * 100 if primary_count != 0 else 0
        return delta
