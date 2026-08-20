"""Run Schemathesis against the committed OpenAPI specs.

::

    ./manage.py verify_openapi case-v1 --url http://localhost:8000 \\
        -H "Authorization: ApiKey me@example.com:<key>" \\
        -P domain=my-project -n 50

Schemathesis is a development dependency, so it is imported where it is used
to keep this module importable without it.
"""

import textwrap
from argparse import RawDescriptionHelpFormatter
from collections import defaultdict
from dataclasses import dataclass

from django.core.management.base import (
    BaseCommand,
    CommandError,
    DjangoHelpFormatter,
)

from corehq.apps.api.management.commands.generate_openapi import SPEC_DIR

#: Methods exercised unless ``--methods`` says otherwise. A generated write
#: request would change data in the project space under test.
READ_METHODS = ('GET', 'HEAD')

#: ``bundle.json`` repeats every path in the per-resource documents.
EXCLUDED_SLUGS = frozenset(['bundle'])

#: Scenario statuses, as Schemathesis names them.
FAILING = frozenset(['failure', 'error', 'interrupted'])
SKIPPED = 'skip'
ERROR = 'error'

#: Every phase Schemathesis can run:
# https://schemathesis.readthedocs.io/en/stable/explanations/data-generation/
PHASES = ('examples', 'coverage', 'fuzzing', 'stateful')

#: ``stateful`` is left out because following a link runs the operation it
#: points at, which turns a read run into a write run.
DEFAULT_PHASES = ('examples', 'coverage', 'fuzzing')

#: The phase ``--once`` runs: the only one that sends exactly one request per
#: operation with no optional parameters.
ONCE_PHASE = 'fuzzing'

#: ``--mode`` values, as Schemathesis generation modes.
MODES = {
    'positive': ('positive',),
    'negative': ('negative',),
    'all': ('positive', 'negative'),
}

#: Schemathesis would default to both. Invalid data makes these resources
#: answer 400 where the specs document only 200, so every correct rejection
#: reads as an undocumented status code.
DEFAULT_MODES = MODES['positive']

#: The project space placeholder in the generated paths. Every other path
#: parameter identifies a single record.
DOMAIN_PARAMETER = 'domain'

#: Documents with no list endpoint of their own. ``report-data-v1`` is
#: addressed by report configuration id, which ``report-config-v1`` lists.
IDENTIFIER_SOURCES = {'report-data-v1': 'report-config-v1'}

#: Tastypie serialises a record's identifier as ``id``; resources addressed by
#: a named parameter repeat it under that name, which is preferred.
FALLBACK_IDENTIFIER = 'id'

INSTALL_HINT = (
    'Schemathesis is not installed. It is a development dependency, because '
    'nothing but this command needs it: run `uv sync` to get it.'
)

#: Shown under the options: the flags that separate the two ways to run this
#: mean little on their own.
EPILOG = """
There are two ways to run this.

  Validation check. One predictable request per operation, response validated
  against the document that described it. Quick enough to run after a change:

    ./manage.py verify_openapi case-v1 --once \\
        --url http://localhost:8000 \\
        -H "Authorization: ApiKey me@example.com:<key>" \\
        -P domain=my-project

  Property-based testing. Requests generated from the parameter schemas, as
  many per operation as -n says, with any failure shrunk to a minimal input:

    ./manage.py verify_openapi case-v1 -n 100 \\
        --url http://localhost:8000 \\
        -H "Authorization: ApiKey me@example.com:<key>" \\
        -P domain=my-project
"""


class HelpFormatter(DjangoHelpFormatter, RawDescriptionHelpFormatter):
    """Django's option ordering, with :data:`EPILOG` left as it is written."""


@dataclass(frozen=True)
class Result:
    """What one operation did in one test phase."""

    label: str
    phase: str
    status: str
    #: One entry per distinct failure or error.
    details: tuple = ()

    @property
    def failed(self):
        return self.status in FAILING

    def __str__(self):
        line = f'{self.status:8} {self.phase:9} {self.label}'
        body = '\n'.join(textwrap.indent(d, '    ') for d in self.details)
        return f'{line}\n{body}' if body else line


def spec_paths(slugs=None, spec_dir=SPEC_DIR):
    """The documents to check, in a stable order.

    ``slugs`` names documents, e.g. ``['case-v1']``; empty means all but
    :data:`EXCLUDED_SLUGS`, though naming one of those is honoured.
    """
    paths = sorted(spec_dir.glob('*.json'))
    if not slugs:
        return [path for path in paths if path.stem not in EXCLUDED_SLUGS]
    chosen = [path for path in paths if path.stem in set(slugs)]
    missing = set(slugs) - {path.stem for path in chosen}
    if missing:
        raise ValueError(f'No such spec: {", ".join(sorted(missing))}')
    return chosen


def parse_pairs(values, separator):
    """``['a: b', 'c: d']`` as ``{'a': 'b', 'c': 'd'}``.

    Only the first separator splits, so a header value may contain one.
    """
    pairs = {}
    for value in values:
        name, found, rest = value.partition(separator)
        if not found or not name.strip():
            raise ValueError(f'Expected NAME{separator}VALUE, got "{value}".')
        pairs[name.strip()] = rest.strip()
    return pairs


def split_list(value, *, upper=False):
    """``'a, b'`` as ``['a', 'b']``."""
    items = [item.strip() for item in value.split(',') if item.strip()]
    if not items:
        raise ValueError(f'Expected a comma-separated list, got "{value}".')
    return [item.upper() for item in items] if upper else items


def positive_int(value):
    """An ``argparse`` type: a count of at least one."""
    number = int(value)
    if number < 1:
        raise ValueError(f'Expected a positive integer, got "{value}".')
    return number


def parse_phases(value):
    phases = split_list(value)
    unknown = [phase for phase in phases if phase not in PHASES]
    if unknown:
        raise ValueError(
            f'No such phase: {", ".join(unknown)}. '
            f'Choose from {", ".join(PHASES)}.'
        )
    return phases


def load_schema(path, *, base_url, headers=None, parameters=None,
                max_examples=None, modes=DEFAULT_MODES, methods=READ_METHODS,
                phases=DEFAULT_PHASES, deterministic=False, exclude_paths=()):
    """One committed document, configured for the run."""
    try:
        import schemathesis
        from schemathesis import GenerationMode
    except ImportError as exc:
        raise CommandError(INSTALL_HINT) from exc

    schema = schemathesis.openapi.from_path(path)
    schema.config.update(
        base_url=base_url,
        headers=headers or {},
        parameters=parameters or {},
    )
    schema.config.generation.update(
        max_examples=max_examples,
        modes=[GenerationMode(mode) for mode in modes],
        deterministic=deterministic,
        database='none' if deterministic else None,
    )
    schema.config.phases.update(phases=list(phases))
    schema = schema.include(method=list(methods))
    return schema.exclude(path=list(exclude_paths)) if exclude_paths else schema


def read_operations(schema):
    """The operations in a document, skipping any that fail to parse."""
    from schemathesis.core.result import Ok

    for result in schema.get_all_operations():
        if isinstance(result, Ok):
            yield result.ok()


def identifier_parameter(operation):
    """The path parameter naming a single record, if there is one.

    ``/api/case/v1/`` has none; ``/api/case/v1/{pk}/`` is addressed by ``pk``.
    """
    for parameter in operation.path_parameters:
        if parameter.name != DOMAIN_PARAMETER:
            return parameter.name
    return None


def list_records(path, *, base_url, headers=None, parameters=None,
                 spec_dir=SPEC_DIR):
    """The records a document's list endpoint returns, for harvesting ids.

    One plain request rather than a generated one, so a detail endpoint's
    identifier does not depend on what Hypothesis produced.
    :data:`IDENTIFIER_SOURCES` redirects documents with no list endpoint.
    """
    slug = IDENTIFIER_SOURCES.get(path.stem)
    if slug:
        path = spec_dir / f'{slug}.json'
    schema = load_schema(
        path, base_url=base_url, headers=headers, parameters=parameters,
    )
    operation = next(
        (candidate for candidate in read_operations(schema)
         if identifier_parameter(candidate) is None),
        None,
    )
    if operation is None:
        return []

    names = {parameter.name for parameter in operation.path_parameters}
    case = operation.Case(path_parameters={
        name: value for name, value in (parameters or {}).items()
        if name in names
    })
    try:
        response = case.call(base_url=base_url, headers=headers)
    except Exception:
        # Failing here only means no identifier to pin; the run reports the
        # unreachable endpoint itself.
        return []
    if response.status_code != 200:
        return []
    try:
        payload = response.json()
    except ValueError:
        return []
    if not isinstance(payload, dict):
        return []
    return [
        record for record in payload.get('objects') or []
        if isinstance(record, dict)
    ]


def identifier_value(record, name):
    """A record's identifier as a string: its ``name`` key, else ``id``.

    ``True`` is an ``int`` in Python, so booleans are rejected explicitly.
    """
    for key in (name, FALLBACK_IDENTIFIER):
        value = record.get(key)
        if isinstance(value, (str, int)) and not isinstance(value, bool):
            return str(value)
    return None


def harvest_identifiers(path, *, base_url, headers=None, parameters=None,
                        spec_dir=SPEC_DIR):
    """Identifiers for a document's detail endpoints, from its list endpoint.

    Returns the values found, keyed by path parameter name, and the paths whose
    identifier was not found, keyed to the name they wanted -- an empty project
    space yields none. Names already in ``parameters`` are left alone.
    """
    schema = load_schema(
        path, base_url=base_url, headers=headers, parameters=parameters,
    )
    wanted = defaultdict(list)
    for operation in read_operations(schema):
        name = identifier_parameter(operation)
        if name is not None and name not in (parameters or {}):
            wanted[name].append(operation.path)
    if not wanted:
        return {}, {}

    found = {}
    records = list_records(
        path, base_url=base_url, headers=headers, parameters=parameters,
        spec_dir=spec_dir,
    )
    for record in records:
        for name in list(wanted):
            value = identifier_value(record, name)
            if value is not None:
                found[name] = value
                del wanted[name]
        if not wanted:
            break
    unresolved = {
        path_: name for name, paths in wanted.items() for path_ in paths
    }
    return found, unresolved


def describe_failures(recorder):
    """The distinct check failures a scenario recorded, ready to print.

    Deduplicated by what they say, since one bad schema fails identically for
    most generated cases. The code sample is a curl reproduction.
    """
    described = {}
    for checks in recorder.checks.values():
        for check in checks:
            if check.failure_info is None:
                continue
            failure = check.failure_info.failure
            key = (check.name, failure.title, failure.message)
            described.setdefault(key, '\n'.join([
                f'{check.name}: {failure.title}',
                failure.message,
                check.failure_info.code_sample,
            ]))
    return list(described.values())


def check_spec(path, **options):
    """Yield a :class:`Result` per operation per phase, as they finish.

    Schemathesis sends one ``GET`` to probe the instance before any phase, which
    no configuration here turns off.
    """
    from schemathesis.engine import events, from_schema

    schema = load_schema(path, **options)

    # Errors arrive as their own events, one per generated case, ahead of the
    # scenario they belong to. Kept by exception class so an unreachable
    # instance reads as one line per operation rather than one per URL.
    errors = defaultdict(dict)
    for event in from_schema(schema).execute():
        if isinstance(event, events.NonFatalError):
            errors[event.label].setdefault(
                type(event.value).__name__, str(event.value),
            )
        elif isinstance(event, events.FatalError):
            yield Result(path.stem, 'Fatal', ERROR, (str(event.exception),))
        elif isinstance(event, events.ScenarioFinished):
            details = describe_failures(event.recorder)
            details.extend(errors.pop(event.label, {}).values())
            yield Result(
                event.label,
                event.phase.value,
                event.status.value,
                tuple(details),
            )


class Command(BaseCommand):
    # Wrapped by hand: HelpFormatter leaves the description as written.
    help = (
        'Send requests built from the committed OpenAPI specs to a running\n'
        'instance and check that the responses match the specs. Use --once for\n'
        'a validation check, or -n N for property-based testing; the examples\n'
        'below show both. Only read methods are exercised. Exits non-zero on\n'
        'any mismatch.'
    )

    def create_parser(self, prog_name, subcommand, **kwargs):
        return super().create_parser(
            prog_name,
            subcommand,
            epilog=EPILOG,
            formatter_class=HelpFormatter,
            **kwargs,
        )

    def add_arguments(self, parser):
        parser.add_argument(
            'slugs',
            nargs='*',
            metavar='SLUG',
            help='Check only these documents, e.g. case-v1. Defaults to all.',
        )
        parser.add_argument(
            '--url',
            required=True,
            help='Base URL of the instance under test, e.g. '
            'http://localhost:8000.',
        )
        parser.add_argument(
            '-H', '--header',
            action='append',
            default=[],
            dest='headers',
            metavar='NAME:VALUE',
            help='Header to send with every request. Repeatable. These '
            'resources need credentials: -H "Authorization: ApiKey '
            'user@example.com:<key>".',
        )
        parser.add_argument(
            '-P', '--param',
            action='append',
            default=[],
            dest='parameters',
            metavar='NAME=VALUE',
            help='Pin a parameter instead of generating it. The project space '
            'always needs one, -P domain=my-project. A detail endpoint\'s '
            'identifier is harvested from its list endpoint, but -P pk=<id> '
            'overrides that.',
        )
        parser.add_argument(
            '--no-harvest',
            action='store_false',
            dest='harvest',
            help='Do not call each list endpoint for an identifier to address '
            'its detail endpoint with. Without one, a detail endpoint is '
            'skipped unless -P pins it.',
        )
        parser.add_argument(
            '-n', '--max-examples',
            type=positive_int,
            help='Generated requests per operation. Every one is a real '
            'request, so this sets how long a run takes. Schemathesis '
            'defaults to 100.',
        )
        parser.add_argument(
            '--once',
            action='store_true',
            help='Validate rather than fuzz: send one request per operation, '
            'carrying nothing but the parameters given here, and check the '
            'response. The same request every run. Cannot be combined with '
            f'--phases or -n. (It runs the {ONCE_PHASE} phase with a single '
            'fixed example, so that is what the results are labelled.)',
        )
        parser.add_argument(
            '-m', '--mode',
            choices=sorted(MODES),
            default='positive',
            help='Generate data that satisfies the schema (positive), '
            'deliberately violates it (negative), or both. Default: positive. '
            'Anything else reports every 400 the resources correctly return '
            'as an undocumented status code, and lets the coverage phase try '
            'methods a path does not document.',
        )
        parser.add_argument(
            '--methods',
            default=','.join(READ_METHODS),
            metavar='GET,POST',
            help='Methods to exercise. Anything beyond the default '
            f'{",".join(READ_METHODS)} writes to the project space under '
            'test with generated payloads.',
        )
        parser.add_argument(
            '--phases',
            metavar=','.join(DEFAULT_PHASES),
            help=f'Test phases to run, from {", ".join(PHASES)}. Default: '
            f'{", ".join(DEFAULT_PHASES)}. Stateful is left out because '
            'following a link runs the operation it points at, which is how a '
            'read turns into a write.',
        )

    def handle(self, slugs, url, headers, parameters, harvest, max_examples,
               once, mode, methods, phases, **kwargs):
        if once and (phases is not None or max_examples is not None):
            raise CommandError(
                f'--once means --phases {ONCE_PHASE} -n 1; drop the other.'
            )
        try:
            paths = spec_paths(slugs)
            options = {
                'base_url': url,
                'headers': parse_pairs(headers, ':'),
                'parameters': parse_pairs(parameters, '='),
                'max_examples': 1 if once else max_examples,
                'modes': MODES[mode],
                'methods': split_list(methods, upper=True),
                'phases': [ONCE_PHASE] if once else parse_phases(
                    phases or ','.join(DEFAULT_PHASES)
                ),
                'deterministic': once,
            }
        except ValueError as exc:
            raise CommandError(str(exc))

        passed = failed = skipped = 0
        for path in paths:
            self.stdout.write(self.style.MIGRATE_HEADING(f'{path.stem}:'))
            for result in self.check_document(path, options, harvest=harvest):
                style = self.style.ERROR if result.failed else self.style.SUCCESS
                self.stdout.write(style(textwrap.indent(str(result), '  ')))
                if result.failed:
                    failed += 1
                elif result.status == SKIPPED:
                    skipped += 1
                else:
                    passed += 1

        if failed:
            raise CommandError(f'{failed} checks did not pass.')
        if not passed and not skipped:
            # Otherwise a typo in --methods reads as a clean run.
            raise CommandError('No operations matched. Nothing was checked.')
        summary = f'{passed} check{"" if passed == 1 else "s"} passed'
        if skipped:
            summary += f', {skipped} skipped'
        self.stdout.write(self.style.SUCCESS(f'{summary}.'))

    def check_document(self, path, options, *, harvest):
        """Check one document, harvesting identifiers for it first.

        Not named ``check``: that is Django's system-checks hook.
        """
        options = dict(options)
        unresolved = {}
        if harvest:
            found, unresolved = harvest_identifiers(
                path,
                base_url=options['base_url'],
                headers=options['headers'],
                parameters=options['parameters'],
            )
            if found:
                options['parameters'] = {**options['parameters'], **found}
                pinned = ', '.join(
                    f'{name}={value}' for name, value in found.items()
                )
                self.stdout.write(f'  harvested {pinned}')
        for endpoint, name in unresolved.items():
            yield Result(
                f'GET {endpoint}', 'Harvest', SKIPPED,
                (f'no {name} to address a record with: the list endpoint '
                 'returned no records',),
            )
        yield from check_spec(
            path, exclude_paths=tuple(unresolved), **options,
        )
