from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
from django.core.management.base import BaseCommand

from corehq.preindex.accessors import index_design_doc, get_preindex_designs


class Command(BaseCommand):

    def handle(self, **options):
        for design in get_preindex_designs():
            print("Touching", design)
            index_design_doc(design, wait=False)

        for design in get_preindex_designs():
            print("Waiting for", design)
            index_design_doc(design, wait=True)
