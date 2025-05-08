from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from corehq.toggles.sql_models import ToggleEditPermission
from corehq.toggles import ALL_TAGS


def manage_superusers_toggle_permission(tag_slug, superusers, action='add'):
    """Add or remove a list of superusers to/from ToggleEditPermission for a given tag slug."""
    try:
        permission = ToggleEditPermission.get_by_tag_slug(tag_slug)

        if action == 'add':
            if not permission:
                permission = ToggleEditPermission(tag_slug=tag_slug)
            permission.add_users(list(superusers))
        else:
            if not permission or not permission.enabled_users:
                return True
            permission.remove_users(list(superusers))
        return True
    except Exception as e:
        raise CommandError(f"Failed to {action} superusers {'to' if action == 'add' else 'from'} "
                           f"tag '{tag_slug}': {e}")


class Command(BaseCommand):
    help = "Add or remove all superusers to/from Toggle Edit Permission for a given tag slug or all tags."

    def add_arguments(self, parser):
        parser.add_argument(
            '--tag',
            help="Specify a tag slug to grant superusers access. Use 'all' to grant access for all tags.",
            required=True,
        )
        parser.add_argument(
            '--action',
            help="Specify whether to add or remove superusers (add/remove)",
            choices=['add', 'remove'],
            required=True
        )

    def handle(self, *args, **options):
        tag_slug = options['tag']
        action = options['action']
        superusers = User.objects.filter(is_superuser=True).values_list('username', flat=True)

        if not superusers:
            self.stdout.write(self.style.WARNING("No superusers found."))
            return

        if tag_slug == 'all':
            tags = [tag.slug for tag in ALL_TAGS]
        else:
            tags = [tag_slug]

        for tag in tags:
            manage_superusers_toggle_permission(tag, superusers, action)
            self.stdout.write(
                self.style.SUCCESS(f"Superusers {'added to' if action == 'add' else 'removed from'} tag: {tag}")
            )

        self.stdout.write(self.style.SUCCESS("Operation completed successfully."))
