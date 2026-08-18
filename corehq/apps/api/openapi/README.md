# OpenAPI specs for the CommCare data APIs

The specs under `docs/api/spec/` are generated from the API code and committed,
so a change to an API's shape appears as a reviewable diff.

## Regenerating

    ./manage.py generate_openapi

`./manage.py generate_openapi --check` fails if the committed specs are stale.
The same check runs as a test
(`corehq/apps/api/openapi/tests/test_generate_openapi.py`).

## Adding documentation for an API

1. Add the resource version to `catalogue.py` with a `doc_slug`.
2. Give every field a real `help_text`. A field that still carries its field
   type's class default counts as undocumented and fails
   `tests/test_documented_fields.py`.
3. Add a `Docs` inner class with `summary`, `description`, and optionally
   `examples` and `field_schemas`. `Docs` is merged across the class hierarchy,
   so put shared documentation on the base resource and override only what
   changes in a later version.
4. Put JSON examples under `examples/<resource>/<version>/` and reference them
   by relative path.
5. Add the slug to `DOCUMENTED_SLUGS` in `tests/test_documented_fields.py`.
6. Regenerate, and point the `docs/api/*.rst` page at the new spec with the
   `openapi::` directive.

Function-based views use the `@api_docs` decorator in `view_adapter.py` instead
of a `Docs` class.

## Linting

Spectral catches style problems the schema validator accepts, such as a missing
description or `operationId`:

    npx --yes @stoplight/spectral-cli lint \
        --ruleset docs/api/spec/.spectral.yaml \
        docs/api/spec/*.json

It should report no errors. See `docs/api/spec/.spectral.yaml` for the rules
disabled and why (contact/license metadata, which lives on the docs site rather
than in each spec, and trailing-slash paths, which are how CommCare's API
routing actually works).

It should currently report around **30 warnings**, all `operation-description`,
and no other rule. Every one is on an operation belonging to one of the nine
undocumented specs listed below — that count is a real, expected-to-shrink
signal of remaining documentation work, not noise: it should fall as each of
those nine specs gets a real `Docs.description`, and it should reach zero only
once all nine are done. If a warning for a _different_ rule appears, or the
count grows without a corresponding change to those nine specs, something
regressed — investigate rather than assuming it's part of the same baseline.

## Known limitations

- **Tastypie's own `.../schema/` endpoints return HTTP 500** for resources that
  are not `ModelResource` subclasses, because `get_schema()` calls
  `get_object_list()`. That is a pre-existing bug and unrelated to this
  generator, which calls `build_schema()` in-process. See the design doc.

- **Live-response contract coverage is partial.** `tests/test_contract.py`
  validates real HTTP responses against their spec for `user-v1` and `group-v1`
  only. `case-v1` and `form-v1` were left out on setup cost, and the
  function-view endpoints (`case_api`, bulk fetch) are not reachable through
  `APIResourceTest`. Every other documented resource is protected only by
  example-level checks (below), not a live response.

- **The example reverse-check is top-level only.**
  `tests/test_examples_validate.py`'s
  `test_response_example_has_every_declared_field_and_no_others` compares
  top-level property names of the record schema against the example. It does not
  recurse into nested objects or array items, so a mismatch buried inside a
  nested object would not be caught.

- **`OAS30Validator` exempts `readOnly` and `writeOnly` properties from
  `required` checks when there is no request/response context**, which is how it
  is used here. A response example missing a required `readOnly` field would
  therefore pass validation silently.

- **The bulk-array gate depends on examples staying branch-representative.**
  Nothing structurally enforces that a bulk example contains one item per
  `create` branch (e.g. Case API v2 bulk); a uniform single-shape example would
  validate without exercising the branching at all.

- **`sphinxcontrib-openapi` renders only the first branch of an `anyOf`/`oneOf`
  field list.** The rendered example still shows all shapes, so a reader can
  infer the variance, but the generated field list is incomplete for the Case
  API v2 bulk and ext-PUT request bodies.

- **Nine specs are generated but carry no field descriptions:**
  `application-v1`, `bulk-user-v1`, `det-export-v1`, `fixture-v1`,
  `report-config-v1`, `report-data-v1`, `sso-v1`, `user-domains-v1`, and
  `web-user-v1`'s own (non-inherited) fields. They are structurally correct but
  semantically thin, and are deliberately excluded from `DOCUMENTED_SLUGS`. This
  is the plan's first-slice boundary, not an oversight: adding one means writing
  `help_text` for every field, a `Docs` class with a real `description` and at
  least one example, and adding the slug to `DOCUMENTED_SLUGS` per the steps
  above.

- **`jsonschema.RefResolver` is deprecated.** The installed `jsonschema`
  (4.26.0) warns on its use, but the warning is hidden because `pyproject.toml`
  sets `-p no:warnings`. `tests/oas_validation.py` uses it to build a resolver
  for `OAS30Validator`. The replacement is a `referencing.Registry` passed as
  `OAS30Validator(..., registry=...)`. Not migrated yet — tracked here so it is
  not discovered as a hard failure after upstream removes `RefResolver`.
