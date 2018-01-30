from __future__ import absolute_import
from django.core.management.base import BaseCommand

from custom.enikshay.integrations.nikshay.repeater_generator import 

import csv


class Command(BaseCommand):
    def add_arguments(self, parser):