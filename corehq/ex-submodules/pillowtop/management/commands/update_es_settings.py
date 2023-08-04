from django.core.management.base import BaseCommand, CommandError
from corehq.apps.es.index.settings import render_index_tuning_settings

from corehq.apps.es.client import manager as es_manager
from corehq.pillows.utils import get_all_expected_es_indices


class Command(BaseCommand):
    help = "Update dynamic settings for existing elasticsearch indices."

    def add_arguments(self, parser):
        parser.add_argument(
            '--noinput',
            action='store_true',
            dest='noinput',
            default=False,
            help='Skip important confirmation warnings.'
        )

    def handle(self, **options):
        noinput = options.pop('noinput')
        es_indices = list(get_all_expected_es_indices())

        to_update = []

        for adapter in es_indices:
            old_settings = es_manager.index_get_settings(adapter.index_name)
            old_number_of_replicas = int(old_settings['number_of_replicas'])
            new_number_of_replicas = render_index_tuning_settings(adapter.index_name)['number_of_replicas']

            if old_number_of_replicas != new_number_of_replicas:
                print("[{}]:\n  Number of replicas changing from {!r} to {!r}".format(
                    adapter.index_name, old_number_of_replicas, new_number_of_replicas))
                to_update.append((adapter, {
                    'index.number_of_replicas': new_number_of_replicas,
                }))

        if not to_update:
            print("There is nothing to update.")
            return
        if (noinput or _confirm(
                "Confirm that you want to update all the settings above?")):
            for adapter, settings in to_update:
                # TODO: Figure out how we want to handle updating settings on the cluster
                # If we want to keep the same way make _index_put_settings public
                mapping_res = es_manager._index_put_settings(adapter.index_name, settings)
                if mapping_res.get('acknowledged', False):
                    print("{} [{}]:\n  Index settings successfully updated".format(
                        adapter.canonical_name, adapter.index_name))
                else:
                    print(mapping_res)


def _confirm(message):
    if input(
            '{} [y/n]'.format(message)
    ).lower() == 'y':
        return True
    else:
        raise CommandError('abort')
