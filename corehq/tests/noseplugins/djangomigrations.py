"""A plugin to disable django database migrations (saves a lot of time)

Use --no-migrations to disable django database migrations.
"""
from __future__ import absolute_import
from nose.plugins import Plugin


class DjangoMigrationsPlugin(Plugin):
    """Run tests without Django database migrations."""

    # Inspired by https://gist.github.com/NotSqrt/5f3c76cd15e40ef62d09
    # See also https://github.com/henriquebastos/django-test-without-migrations

    name = 'django-migrations'
    enabled = True

    def options(self, parser, env):
        # Do not call super to avoid adding a ``--with`` option for this plugin
        parser.add_option('--no-migrations', action='store_true',
                          dest='no_migrations',
                          default=env.get('NOSE_DISABLE_DJANGO_MIGRATIONS'),
                          help='Disable Django database migrations to save a '
                               'lot of time. [NOSE_DISABLE_DJANGO_MIGRATIONS]')

    def configure(self, options, conf):
        if options.no_migrations:
            from django.conf import settings
            settings.MIGRATION_MODULES = DisableMigrations()


class DisableMigrations(object):

    def __contains__(self, item):
        return True

    def __getitem__(self, item):
        return "notmigrations"
