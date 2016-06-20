import os
from collections import defaultdict

from django.conf import settings
from django.core.management import call_command

from celery.schedules import crontab
from celery.task import periodic_task
from datetime import datetime

from corehq.apps.cleanup.management.commands.fix_xforms_with_undefined_xmlns import \
    parse_log_message, ERROR_SAVING, SET_XMLNS, MULTI_MATCH


def get_summary_stats_from_stream(stream):
    summary = {
        # A dictionary like: {
        #   "foo-domain": 7,
        #   "bar-domain": 3,
        # }
        'not_fixed': defaultdict(lambda: 0),
        'fixed': defaultdict(lambda: 0),
        'errors': defaultdict(lambda: 0),
        'submitting_bad_forms': defaultdict(set),
        'multi_match_builds': set(),
    }

    for line in stream:
        level, event, extras = parse_log_message(line)
        domain = extras.get('domain', '')
        if event == ERROR_SAVING:
            summary['errors'] += 1
        elif event == SET_XMLNS or event == MULTI_MATCH:
            summary['submitting_bad_forms'][domain].add(
                extras.get('username', '')
            )
            if event == SET_XMLNS:
                summary['fixed'][domain] += 1
            if event == MULTI_MATCH:
                summary['not_fixed'][domain] += 1
                summary['multi_match_builds'].add(
                    (domain, extras.get('build_id', ''))
                )
    return summary

def pprint_stats(stats, outstream):
    outstream.write("Number of errors: {}\n".format(sum(stats['errors'].values())))
    outstream.write("Number of xforms that we could not fix: {}\n".format(sum(stats['not_fixed'].values())))
    outstream.write("Number of xforms that we fixed: {}\n".format(sum(stats['fixed'].values())))
    outstream.write("Domains and users that submitted bad xforms:\n")
    for domain, users in sorted(stats['submitting_bad_forms'].items()):
        outstream.write(
            "    {} ({} fixed, {} not fixed, {} errors)\n".format(
                domain, stats['fixed'][domain], stats['not_fixed'][domain], stats['errors'][domain]
            )
        )
        for user in sorted(list(users)):
            outstream.write("        {}\n".format(user))

