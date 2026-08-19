"""Run Schemathesis against the committed OpenAPI specs.

The specs in ``docs/api/spec/`` are generated from the resource classes, so
they cannot drift from the *code*. They can still drift from the *responses*
the code produces: a field that serialises to ``null`` where the schema says
string, a paginator that stops emitting ``total_count``, a declared type that
no longer matches the data behind it. Nothing in the generator notices any of
that, because the generator never makes a request.

`Schemathesis <https://schemathesis.readthedocs.io/>`_ does. It generates
requests from the parameter schemas -- ``limit`` and ``offset`` across the
integer range, every ``order_by`` value, unexpected combinations of the two --
sends them to a running instance, and validates each response against the
document that described it, shrinking any failure to a minimal input.

Requests are real, against a real project space, so only read methods are
exercised by default. See :data:`READ_METHODS`.

::

    ./manage.py verify_openapi case-v1 --url http://localhost:8000 \\
        -H "Authorization: ApiKey me@example.com:<key>" \\
        -P domain=my-project -n 50

Every path but ``user-domains-v1``'s is under ``/a/{domain}/``, so ``-P
domain=`` is all but always needed: a generated project space would only ever
produce a 404, and a 404 is reported as an undocumented status code because
the specs document only 200. A pinned name is matched wherever it appears, so
``-P domain=`` also fills the ``domain`` *query* parameter that the location
resources document alongside the path one.

The identifier a detail endpoint takes is found rather than pinned -- see
:func:`harvest_identifiers` -- though ``-P pk=<case id>`` still wins if given.

``--once`` sends a single predictable request per operation instead of
generating many. See :data:`ONCE_PHASE`.

Schemathesis is a development dependency, since nothing but this command needs
it, so it is imported where it is used rather than at module scope: this module
has to stay importable in environments that do not have it.
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
#: request would create or destroy records in the project space under test.
READ_METHODS = ('GET', 'HEAD')

#: ``bundle.json`` repeats every path in the per-resource documents, so
#: checking it alongside them would test everything twice.
EXCLUDED_SLUGS = frozenset(['bundle'])

#: Statuses that mean the operation did not come back clean.
FAILING = frozenset(['failure', 'error', 'interrupted'])

#: Every phase Schemathesis can run. ``examples`` replays the examples in the
#: document, ``coverage`` walks each parameter's boundary values, ``fuzzing``
#: generates data from the parameter schemas, ``stateful`` follows the links
#: between operations.
PHASES = ('examples', 'coverage', 'fuzzing', 'stateful')

#: Run these unless ``--phases`` says otherwise. ``stateful`` is left out
#: because following a link means running the operation it points at, which is
#: how a read turns into a write.
DEFAULT_PHASES = ('examples', 'coverage', 'fuzzing')

#: The phase ``--once`` runs. Fuzzing is the only one that sends exactly one
#: request per operation and leaves out every optional parameter: ``examples``
#: has nothing to replay, because the generator writes no examples into the
#: documents, and ``coverage`` fills in each parameter's documented default.
ONCE_PHASE = 'fuzzing'

#: ``--mode`` values. Schemathesis generates data that either satisfies the
#: schema or deliberately violates it; ``all`` does both.
MODES = {
    'positive': ('positive',),
    'negative': ('negative',),
    'all': ('positive', 'negative'),
}

#: Generate valid data unless asked otherwise, where Schemathesis would
#: default to both. Invalid data asks a different question and answers it
#: noisily here: these resources reject it with a 400, the specs document only
#: 200, so every correct rejection is reported as an undocumented status code.
#: It also lets the coverage phase try methods a path does not document, which
#: :data:`READ_METHODS` does not constrain.
DEFAULT_MODES = MODES['positive']

#: The project space placeholder in the generated paths. Every other path
#: parameter identifies a single record.
DOMAIN_PARAMETER = 'domain'

#: Where to harvest identifiers for a document that has no list endpoint of
#: its own. ``configurablereportdata`` is addressed by report configuration id
#: -- its ``obj_get`` passes ``pk`` to ``_get_report_configuration`` -- and
#: those are what ``report-config-v1`` lists.
IDENTIFIER_SOURCES = {'report-data-v1': 'report-config-v1'}

#: Tastypie serialises a record's identifier as ``id``. Resources addressed by
#: a named parameter repeat it under that name, so the named key is preferred
#: where a record carries both.
FALLBACK_IDENTIFIER = 'id'

INSTALL_HINT = (
    'Schemathesis is not installed. It is a development dependency, because '
    'nothing but this command needs it: run `uv sync` to get it.'
)

#: Shown under the options. Written out rather than left to the reader to
#: assemble, because the two things this command is for -- checking that
#: responses match the specs, and generating requests to look for cases where
#: they do not -- differ only in flags that mean nothing on their own.
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

  Add -m all to generate invalid data as well, which asks whether the
  resources reject what they should rather than whether they document what
  they return. Expect noise: these specs document only 200, so every 400 a
  resource correctly answers with is reported as an undocumented status code.

Drop the SLUG to check every document. Get an API key from /account/api_keys/.

The identifier a detail endpoint takes is harvested from the list endpoint
alongside it, so the project space needs records in it; endpoints whose
identifier cannot be found are skipped rather than checked. Use -P pk=<id> to
choose the record yourself, or --no-harvest to ask for none.
"""


class HelpFormatter(DjangoHelpFormatter, RawDescriptionHelpFormatter):
    """Django's option ordering, with :data:`EPILOG` left as it is written."""


@dataclass(frozen=True)
class Result:
    """What one operation did in one test phase."""

    label: str
    phase: str
    status: str
    #: One entry per distinct failure or error, ready to print.
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

    ``slugs`` names documents, e.g. ``['case-v1']``. When it is empty
    everything but :data:`EXCLUDED_SLUGS` is checked; naming one of those
    explicitly is honoured.
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

    Only the first separator splits, so a header value may contain one --
    ``Authorization: ApiKey user:key``.
    """
    pairs = {}
    for value in values:
        name, found, rest = value.partition(separator)
        if not found or not name.strip():
            raise ValueError(f'Expected NAME{separator}VALUE, got "{value}".')
        pairs[name.strip()] = rest.strip()
    return pairs


def split_list(value, upper=False):
    """``'a, b'`` as ``['a', 'b']``."""
    items = [item.strip() for item in value.split(',') if item.strip()]
    if not items:
        raise ValueError(f'Expected a comma-separated list, got "{value}".')
    return [item.upper() for item in items] if upper else items


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

    ``/a/{domain}/api/case/v1/`` has none and is a list endpoint;
    ``/a/{domain}/api/case/v1/{pk}/`` is addressed by ``pk``.
    """
    for parameter in operation.path_parameters:
        if parameter.name != DOMAIN_PARAMETER:
            return parameter.name
    return None


def list_records(path, *, base_url, headers=None, parameters=None,
                 spec_dir=SPEC_DIR):
    """The records a document's list endpoint returns, for harvesting ids.

    One plain request, not a generated one, so that what a detail endpoint is
    given does not depend on what Hypothesis happened to produce. A document
    with no list endpoint of its own is redirected by
    :data:`IDENTIFIER_SOURCES`.
    """
    slug = IDENTIFIER_SOURCES.get(path.stem)
    if slug:
        path = spec_dir / f'{slug}.json'
    schema = load_schema(
        path, base_url=base_url, headers=headers, parameters=parameters,
    )
    for operation in read_operations(schema):
        if identifier_parameter(operation) is not None:
            continue
        names = {parameter.name for parameter in operation.path_parameters}
        case = operation.Case(path_parameters={
            name: value for name, value in (parameters or {}).items()
            if name in names
        })
        try:
            response = case.call(base_url=base_url, headers=headers)
            payload = response.json()
        except Exception:
            # A list endpoint that cannot be reached or read is a failure the
            # run itself reports; here it only means no identifier to pin.
            return []
        if response.status_code != 200 or not isinstance(payload, dict):
            return []
        return [
            record for record in payload.get('objects') or []
            if isinstance(record, dict)
        ]
    return []


def harvest_identifiers(path, *, base_url, headers=None, parameters=None,
                        spec_dir=SPEC_DIR):
    """Identifiers that address real records, for a document's detail endpoints.

    A detail endpoint needs an identifier, and rather than have one pinned by
    hand this calls the list endpoint alongside it and takes one out of the
    response. A project space with data in it is therefore a prerequisite.

    Returns the values found, keyed by path parameter name, and the paths whose
    identifier could not be found, keyed to the name they wanted -- because the
    project space holds no records of that kind, or because the list endpoint
    did not answer. Anything already in ``parameters`` is left alone.
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
            value = record.get(name, record.get(FALLBACK_IDENTIFIER))
            if isinstance(value, (str, int)) and not isinstance(value, bool):
                found[name] = str(value)
                del wanted[name]
        if not wanted:
            break
    unresolved = {
        path_: name for name, paths in wanted.items() for path_ in paths
    }
    return found, unresolved


def describe_failures(recorder):
    """The distinct check failures a scenario recorded, ready to print.

    A scenario runs many generated cases, and a schema that does not match the
    data fails identically for most of them, so failures are deduplicated by
    what they say. The code sample is a curl command that reproduces the one
    Schemathesis shrank to.
    """
    described = {}
    for checks in recorder.checks.values():
        for check in checks:
            if check.failure_info is None:
                continue
            failure = check.failure_info.failure
            key = (check.name, failure.title, failure.message)
            described[key] = '\n'.join([
                f'{check.name}: {failure.title}',
                failure.message,
                check.failure_info.code_sample,
            ])
    return list(described.values())


def check_spec(path, **options):
    """Yield a :class:`Result` per operation per phase, as they finish.

    Ahead of the phases named, Schemathesis probes the instance once to work
    out what it tolerates -- a single ``GET``, which no configuration here
    turns off.
    """
    from schemathesis.engine import events, from_schema

    schema = load_schema(path, **options)

    # Errors arrive as their own events, one per generated case, ahead of the
    # scenario they belong to. Held here so that the scenario can report why it
    # failed rather than only that it did, and keyed by exception class so that
    # an unreachable instance reads as one line per operation rather than one
    # per generated URL.
    errors = defaultdict(dict)
    for event in from_schema(schema).execute():
        if isinstance(event, events.NonFatalError):
            errors[event.label].setdefault(
                type(event.value).__name__, str(event.value),
            )
        elif isinstance(event, events.FatalError):
            yield Result('', '', 'error', (str(event.exception),))
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
    # Wrapped by hand: HelpFormatter leaves the description as written, which
    # is what keeps the examples in EPILOG legible.
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
            type=int,
            help='Generated requests per operation. Every one is a real '
            'request, so this sets how long a run takes. Schemathesis '
            'defaults to 100.',
        )
        parser.add_argument(
            '--once',
            action='store_true',
            help='Verify rather than fuzz: send one predictable request per '
            f'operation and check its response. Shorthand for --phases '
            f'{ONCE_PHASE} -n 1 with generation fixed, so the request carries '
            'nothing but the parameters given here. Cannot be combined with '
            '--phases or -n.',
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
        if once and (phases or max_examples):
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
            for result in self.check_document(path, options, harvest):
                self.stdout.write(
                    (self.style.ERROR if result.failed else self.style.SUCCESS)
                    (textwrap.indent(str(result), '  '))
                )
                if result.failed:
                    failed += 1
                elif result.status == 'skip':
                    skipped += 1
                else:
                    passed += 1

        if failed:
            raise CommandError(f'{failed} checks did not pass.')
        if not (passed or skipped):
            # Otherwise a typo in --methods reads as a clean run.
            raise CommandError('No operations matched. Nothing was checked.')
        summary = f'{passed} check{"" if passed == 1 else "s"} passed'
        if skipped:
            summary += f', {skipped} skipped'
        self.stdout.write(self.style.SUCCESS(f'{summary}.'))

    def check_document(self, path, options, harvest):
        """Check one document, harvesting identifiers for it first.

        Not named ``check``: that is Django's system-checks hook, and shadowing
        it breaks every invocation that does not pass ``--skip-checks``.
        """
        options = dict(options)
        excluded = {}
        if harvest:
            found, excluded = harvest_identifiers(
                path,
                base_url=options['base_url'],
                headers=options['headers'],
                parameters=options['parameters'],
            )
            if found:
                options['parameters'] = {**options['parameters'], **found}
                pinned = ', '.join(f'{n}={v}' for n, v in found.items())
                self.stdout.write(f'  harvested {pinned}')
        for path_, name in excluded.items():
            yield Result(
                f'GET {path_}', 'Harvest', 'skip',
                (f'no {name} to address a record with: the list endpoint '
                 'returned no records',),
            )
        yield from check_spec(path, exclude_paths=tuple(excluded), **options)
