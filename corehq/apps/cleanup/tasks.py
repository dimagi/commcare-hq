from collections import defaultdict

from corehq.apps.cleanup.management.commands.fix_xforms_with_undefined_xmlns import \
    parse_log_message, ERROR_SAVING, SET_XMLNS, MULTI_MATCH, \
    CANT_MATCH, FORM_HAS_UNDEFINED_XMLNS


def get_summary_stats_from_stream(stream):
    summary = {
        # A dictionary like: {
        #   "foo-domain": 7,
        #   "bar-domain": 3,
        # }
        # This is the number of xforms that were not fixed because the corresponding
        # build contains multiple forms that had been fixed by the
        # fix_forms_and_apps_with_missing_xmlns management command
        'not_fixed_multi_match': defaultdict(lambda: 0),
        # This is the number of xforms that were not fixed because the corresponding
        # build contains either 0 or more than 1 forms with a matching name.
        'not_fixed_cant_match': defaultdict(lambda: 0),
        # This is the number of xforms that were not fixed because the corresponding
        # build contains forms that currently have an "undefined" xmlns. This
        # violates the assumption that all apps and builds had been repaired.
        'not_fixed_undefined_xmlns': defaultdict(lambda: 0),
        # This is the number of xforms that had their xmlns replaced successfully
        'fixed': defaultdict(lambda: 0),
        'errors': defaultdict(lambda: 0),
        # A dictionary like : {
        #   "foo-domain": {"user1", "user2"}
        # }
        # showing which users are need to update their apps so that they stop
        # submitting forms with "undefined" xmlns.
        'submitting_bad_forms': defaultdict(set),
        'multi_match_builds': set(),
        'cant_match_form_builds': set(),
        'builds_with_undefined_xmlns': set(),
    }

    for line in stream:
        level, event, extras = parse_log_message(line)
        domain = extras.get('domain', '')
        if event == ERROR_SAVING:
            summary['errors'] += 1
        if event in [SET_XMLNS, MULTI_MATCH, FORM_HAS_UNDEFINED_XMLNS, CANT_MATCH]:
            summary['submitting_bad_forms'][domain].add(extras.get('username', ''))
        if event == SET_XMLNS:
            summary['fixed'][domain] += 1
        elif event == MULTI_MATCH:
            summary['not_fixed_multi_match'][domain] += 1
            summary['multi_match_builds'].add((domain, extras.get('build_id', '')))
        elif event == CANT_MATCH:
            summary['not_fixed_cant_match'][domain] += 1
            summary['cant_match_form_builds'].add((domain, extras.get('build_id', '')))
        elif event == FORM_HAS_UNDEFINED_XMLNS:
            summary['not_fixed_undefined_xmlns'][domain] += 1
            summary['builds_with_undefined_xmlns'].add((domain, extras.get('build_id', '')))

    return summary


def pprint_stats(stats, outstream):
    outstream.write("Number of errors: {}\n".format(sum(stats['errors'].values())))
    outstream.write(
        "Number of xforms that we could not fix (multi match): {}\n".format(
            sum(stats['not_fixed_multi_match'].values()))
    )
    outstream.write(
        "Number of xforms that we could not fix (cant match): {}\n".format(
            sum(stats['not_fixed_cant_match'].values())
        )
    )
    outstream.write(
        "Number of xforms that we could not fix (undef xmlns): {}\n".format(
            sum(stats['not_fixed_undefined_xmlns'].values())
        )
    )
    outstream.write("Number of xforms that we fixed: {}\n".format(
        sum(stats['fixed'].values()))
    )
    outstream.write("Domains and users that submitted bad xforms:\n")
    for domain, users in sorted(stats['submitting_bad_forms'].items()):
        outstream.write(
            "    {} ({} fixed, {} not fixed (multi), {} not fixed (cant_match),"
            " {} not fixed (undef xmlns), {} errors)\n".format(
                domain,
                stats['fixed'][domain],
                stats['not_fixed_multi_match'][domain],
                stats['not_fixed_cant_match'][domain],
                stats['not_fixed_undefined_xmlns'][domain],
                stats['errors'][domain],
            )
        )
        for user in sorted(list(users)):
            outstream.write("        {}\n".format(user))

