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
   changes in a later version. A `field_schemas` key must name a field the
   resource declares; a key it adds outside tastypie's field machinery (in a
   `dehydrate()` override, say) goes in `added_fields` instead, where the entry
   is the property's whole schema. Filing one under the other's key is an error,
   not a silent miss -- see `docs.reject_misfiled_docs`.
4. Put JSON examples under `examples/<resource>/<version>/` and reference them
   by relative path.
5. Add the slug to `DOCUMENTED_SLUGS` in `tests/test_documented_fields.py`.
6. Regenerate, run `yarn openapi:docs`, and confirm the API appears at
   `/api/docs/` with full description coverage. The `docs/api/*.rst` page gets a
   sentence and a link to the reference page, not a directive.

Function-based views use the `@api_docs` decorator in `view_declarations.py` instead
of a `Docs` class, and are catalogued as `ViewEntry` rather than `ApiEntry`.
Steps 2, 3 and 5 do not apply — a view has no tastypie metadata to derive from,
so it declares its request and response schemas whole. The equivalent guards are
in `tests/test_view_docs.py`, and they are not opt-in: a catalogued view must
declare a summary and description, must publish a description for every response
field it documents, and every `examples` key it declares must be one the builder
actually looks up (`<method>_request`, plain or keyed by
`(path, method_request)` — anything else is never read, so the example silently
never reaches the spec). `tests/test_case_v2_urls.py` holds the routed-URL
coverage, deriving the path namespace it walks from the views' own declared
paths, so it needs no change when a second view is documented.

## Linting

`yarn openapi:lint` catches style problems the schema validator accepts, such as
a missing description or `operationId`. CI runs it on every pull request, so an
error fails the build rather than waiting to be noticed.

    yarn openapi:lint

The linter is Redocly (`@redocly/cli`), configured by `redocly.yaml` at the
repository root — the same tool that builds the reference pages, so the project
carries one OpenAPI toolchain rather than two. `redocly.yaml` records which
rules are disabled and why: contact and licence metadata, which live on the docs
site rather than in each spec, and trailing-slash paths, which are how
CommCare's API routing actually works.

It should report **no errors**. It currently reports around **164 warnings**,
which do not fail the run:

| Rule                                      | Count | What it means                                                                          |
| ----------------------------------------- | ----- | -------------------------------------------------------------------------------------- |
| `operation-4xx-response`                  | ~136  | No 4xx response is declared. Most operations document only their success shape so far. |
| `tag-description`                         | ~18   | A tag carries no description.                                                          |
| `no-invalid-media-type-examples`          | ~6    | An example does not validate against its own schema.                                   |
| `no-required-schema-properties-undefined` | ~4    | A schema lists a property in `required` that it does not define.                       |

That count is a real, expected-to-shrink signal of remaining documentation work,
not noise. If a warning for a rule outside this table appears, or a count grows
without a corresponding spec change, something regressed — investigate rather
than assuming it is part of the baseline.

## Known limitations

- **Tastypie's own `.../schema/` endpoints return HTTP 500** for resources that
  are not `ModelResource` subclasses, because `get_schema()` calls
  `get_object_list()`. That is a pre-existing bug and unrelated to this
  generator, which calls `build_schema()` in-process.

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

- **Branching response schemas are where tooling tends to silently
  under-report.** A schema keyed by `$ref`, `anyOf`, `oneOf` or `allOf` caught
  out two different tools here. The old `sphinxcontrib-openapi` renderer (since
  removed in favour of Redoc, which renders every branch) showed only the first
  branch of an `anyOf`/`oneOf` field list. `description_coverage` in
  `response_fields.py` had the same blindness at first: it read
  `schema['properties']` directly, so a branching schema contributed zero fields
  to the count, until a `_record_property_items` traversal was added that
  follows refs and branches. If a coverage or lint number ever looks too good
  (or too bad) on a resource with branching bodies, check whether the tool is
  walking into the branches at all before trusting the count.

- **Nine specs are generated but are still semantically thin:**
  `application-v1`, `bulk-user-v1`, `det-export-v1`, `fixture-v1`,
  `report-config-v1`, `report-data-v1`, `sso-v1`, `user-domains-v1`, and
  `web-user-v1`'s own (non-inherited) fields. Six of them describe exactly one
  field -- `resource_uri`, which every resource now gets centrally from
  `declarations.DEFAULT_FIELD_SCHEMAS` -- so a coverage badge of `1/10` on the
  index page means "nothing has been written for this API yet", not "one field
  was missed". `sso-v1` declares no response fields at all, `user-domains-v1`
  describes neither of its two, and `web-user-v1` sits at 9 of 19, describing
  what it inherits from `user-v1` and none of its own. They are structurally
  correct and deliberately excluded from `DOCUMENTED_SLUGS`: a first-slice
  boundary, not an oversight. Adding one means writing `help_text` for every
  field, a `Docs` class with a real `description` and at least one example, and
  adding the slug to `DOCUMENTED_SLUGS` per the steps above.

- **`jsonschema.RefResolver` is deprecated.** The installed `jsonschema`
  (4.26.0) warns on its use, but the warning is hidden because `pyproject.toml`
  sets `-p no:warnings`. `tests/oas_validation.py` uses it to build a resolver
  for `OAS30Validator`. The replacement is a `referencing.Registry` passed as
  `OAS30Validator(..., registry=...)`. Not migrated yet — tracked here so it is
  not discovered as a hard failure after upstream removes `RefResolver`.
