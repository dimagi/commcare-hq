from corehq.apps.commtrack.models import CommtrackConfig
from django.core.management.base import BaseCommand
from dimagi.utils.couch.database import iter_docs
from corehq.apps.domain.models import Domain


def migrate_data_command(view, fetch_class, process_fn, save_class=None, save_fn=None):
    save_class = save_class or fetch_class
    to_save = []
    relevant_ids = set([r['id'] for r in view.all()])

    for location in iter_docs(fetch_class.get_db(), relevant_ids):
        result = process_fn(location)
        if result[0]:
            to_save.append(result[1])

            if len(to_save) > 500:
                save_class.get_db().bulk_save(to_save)
                to_save = []

    if to_save:
        save_class.get_db().bulk_save(to_save)


class Command(BaseCommand):
    def handle(self, *args, **options):
        view = CommtrackConfig.get_db().view(
            'commtrack/domain_config',
            reduce=False
        )

        # preload domains
        domains_map = {
            d.name: d for d in Domain.get_all()
        }

        """
        Default mode is to only copy types over to
        the domain objects. This is meant to be run after
        preindexing.

        Note this will run on both pre and post deploy instances
        to make sure there aren't any new changes the second time.
        """
        def _process_fn(config):
            if 'location_types' in config:
                domain = domains_map[config['domain']].to_json()
                domain['location_types'] = config['location_types']
                return True, domain

            return False, None

        migrate_data_command(
            view=view,
            fetch_class=CommtrackConfig,
            process_fn=_process_fn,
            save_class=Domain
        )

        if 'post_deploy' in args:
            """
            If user explicitly triggers post_deploy flag,
            then we will actually delete from the commtrack
            config objects.
            """
            def _post_process_fn(config):
                if 'location_types' in config:
                    del config['location_types']
                    return True, config
                else:
                    return False, None

            migrate_data_command(
                view=view,
                fetch_class=CommtrackConfig,
                process_fn=_post_process_fn,
            )
