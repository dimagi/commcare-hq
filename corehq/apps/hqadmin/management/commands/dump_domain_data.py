from collections import OrderedDict

from django.apps import apps
from django.conf import settings
from django.core import serializers
from django.core.management.base import BaseCommand, CommandError
from django.db import router

from corehq.sql_db.config import partition_config

app_labels = {
    'locations.LocationType': 'domain',
    'locations.SQLLocation': 'domain',
    'form_processor.XFormInstanceSQL': 'domain'
}


class Command(BaseCommand):
    help = "Dump a domain's data to disk."
    args = '<domain>'

    def add_arguments(self, parser):
        parser.add_argument('-e', '--exclude', dest='exclude', action='append', default=[],
            help='An app_label or app_label.ModelName to exclude '
                 '(use multiple --exclude to exclude multiple apps/models).')
        parser.add_argument('--indent', default=None, dest='indent', type=int,
                            help='Specifies the indent level to use when pretty-printing output.')
        parser.add_argument('-o', '--output', default=None, dest='output',
            help='Specifies file to which the output is written.')

    def handle(self, domain, **options):
        format = 'json'
        indent = options.get('indent')
        excludes = options.get('exclude')
        output = options.get('output')
        show_traceback = options.get('traceback')

        _check_serialization_format(format)

        excluded_apps, excluded_models = _get_excluded_apps_and_models(excludes)
        app_list = _get_app_list(excluded_apps)

        def get_objects():
            # Collate the objects to be serialized.
            for model in serializers.sort_dependencies(app_list.items()):
                if model in excluded_models:
                    continue

                using = router.db_for_read(model)
                if settings.USE_PARTITIONED_DATABASE and using == partition_config.get_proxy_db():
                    using = partition_config.get_form_processing_dbs()
                else:
                    using = [using]

                for db_alias in using:
                    if not model._meta.proxy and router.allow_migrate_model(db_alias, model):
                        objects = model._default_manager

                        label = '{}.{}'.format(model._meta.app_label, model.__name__)
                        filter_kwarg = app_labels[label]

                        queryset = objects.using(db_alias) \
                            .filter(**{filter_kwarg: domain}) \
                            .order_by(model._meta.pk.name)

                        for obj in queryset.iterator():
                            yield obj

        try:
            self.stdout.ending = None
            stream = open(output, 'w') if output else None
            try:
                serializers.serialize(format, get_objects(), indent=indent,
                        use_natural_foreign_keys=False,
                        use_natural_primary_keys=False,
                        stream=stream or self.stdout)
            finally:
                if stream:
                    stream.close()
        except Exception as e:
            if show_traceback:
                raise
            raise CommandError("Unable to serialize database: %s" % e)


def _get_excluded_apps_and_models(excludes):
    excluded_apps = set()
    excluded_models = set()
    for exclude in excludes:
        if '.' in exclude:
            try:
                model = apps.get_model(exclude)
            except LookupError:
                raise CommandError('Unknown model in excludes: %s' % exclude)
            excluded_models.add(model)
        else:
            try:
                app_config = apps.get_app_config(exclude)
            except LookupError:
                raise CommandError('Unknown app in excludes: %s' % exclude)
            excluded_apps.add(app_config)
    return excluded_apps, excluded_models


def _get_app_list(excluded_apps):
    """
    :return: OrderedDict((model, filter_kwarg), ...)
    """
    app_list = OrderedDict()
    for label in app_labels:
        app_label, model_label = label.split('.')
        try:
            app_config = apps.get_app_config(app_label)
        except LookupError:
            raise CommandError("Unknown application: %s" % app_label)
        if app_config in excluded_apps:
            continue
        try:
            model = app_config.get_model(model_label)
        except LookupError:
            raise CommandError("Unknown model: %s.%s" % (app_label, model_label))

        app_list_value = app_list.setdefault(app_config, [])

        if model not in app_list_value:
            app_list_value.append(model)

    return app_list


def _check_serialization_format(format):
    # Check that the serialization format exists; this is a shortcut to
    # avoid collating all the objects and _then_ failing.
    if format not in serializers.get_public_serializer_formats():
        try:
            serializers.get_serializer(format)
        except serializers.SerializerDoesNotExist:
            pass

        raise CommandError("Unknown serialization format: %s" % format)
