import logging
from django.core.mail import send_mail
from django.core.management.base import  BaseCommand
from casexml.apps.case.models import CommCareCase
from corehq.apps.hqcase.management.commands.ptop_fast_reindexer import PtopReindexer
from corehq.pillows import CasePillow

CHUNK_SIZE=500
POOL_SIZE = 15




class Command(PtopReindexer):
    help = "Fast reindex of case elastic index by using the case view and reindexing cases"

    doc_class = CommCareCase
    view_name = 'case/by_owner'
    pillow_class = CasePillow
