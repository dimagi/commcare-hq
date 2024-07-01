from corehq.apps.celery import task


@task(queue='background_queue', ignore_result=True)
def process_updates_for_village_async(domain, village, dry_run):
    from custom.benin.management.commands.migrate_users_and_their_cases_to_new_rc_level import \
        process_updates_for_village
    process_updates_for_village(domain, village, dry_run)
