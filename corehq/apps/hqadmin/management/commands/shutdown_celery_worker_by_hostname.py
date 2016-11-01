from django.core.management.base import BaseCommand
from django.conf import settings
from celery import Celery


class Command(BaseCommand):
    help = "Gracefully shutsdown a celery worker"
    args = 'hostname'

    def handle(self, hostname, *args, **options):
        celery = Celery()
        celery.config_from_object(settings)
        celery.control.broadcast('shutdown', destination=[hostname])
