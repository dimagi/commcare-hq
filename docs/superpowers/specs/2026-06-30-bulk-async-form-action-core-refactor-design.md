# SAAS-19975: Refactor `archive_or_restore_forms` into a BulkAsyncJob-ready core

## Context

This is pure-refactor groundwork for the larger **Bulk Form Actions API**
effort (epic SAAS-19558), which adds an async, domain-scoped HTTP API to
archive / unarchive / delete forms in bulk. The eventual cutover ticket
(SAAS-19895) replaces soil / `DownloadBase` with the `BulkAsyncJob` model as
the persistence + status layer for both the existing bulk-archive UI and the
new API, and adds `delete` as a third action.

This ticket sets up the building blocks so that the cutover can be a focused
swap of persistence + worker, **without** also refactoring the iteration loop
at the same time.

Dependencies:

- **SAAS-19893** — `BulkAsyncJob` model + `CODES.bulk_async_job` blob code.
  Done (present on this branch; `CODES.bulk_async_job = 18`).
- This ticket does **not** depend on the tombstone work (SAAS-19704); `delete`
  is added later in the cutover.

## Goal

Extract a pure, structured core out of
`corehq/apps/data_interfaces/utils.py:archive_or_restore_forms`, and add blob
read/write helpers for the `BulkAsyncJob` payloads — with **no behavior
change** to the existing UI flow, save for one small, intentional, documented
change (see below).

## Deliverables

1. **Blob helpers** for `CODES.bulk_async_job` — write/read the two JSON
   payloads the cutover will persist:
   - `requested_ids` payload: `{"requested_ids": [<id>, ...]}`
   - `skipped_ids` payload: `[{"id": <id>, "reason": <reason>}, ...]`

   Built and unit-tested standalone in this ticket. They are **not** wired
   into the live shim path here — the shim continues to use `DownloadBase`.
   The cutover (SAAS-19895) is the first consumer.

2. **Pure core** extracted from `archive_or_restore_forms`:

   ```python
   def iter_form_action_results(domain, form_ids, action_fn) -> Iterator[FormActionResult]:
       ...
   ```

   - No i18n, no `DownloadBase` progress, no `from_excel` branch.
   - `action_fn` is a callable applied to each in-scope `XFormInstance`
     (e.g. `xform.archive` / `xform.unarchive`). The future `delete` action
     passes its own callable in the cutover.
   - Yields one `FormActionResult` per requested id.

3. **Re-implement `archive_or_restore_forms` as a thin shim** over the new
   core, re-adding today's `{"messages": ...}` shape, i18n strings, and
   `DownloadBase` progress, so the existing Celery task
   `bulk_form_management_async` and the UI are unchanged. The shim is
   throwaway scaffolding — deleted in the cutover.

4. **Tests** (see Testing strategy).

## Data shapes

```python
@dataclass(frozen=True)
class FormActionResult:
    form_id: str
    status: str                  # 'succeeded' | 'skipped'
    reason: str | None = None    # 'not_found' | 'unexpected_error'; None on success
```

Reasons emitted by this ticket's core: `not_found` and `unexpected_error`.
The richer reasons in the API spec (`deleted`, `not_archived`,
`already_unarchived`) arrive with the `delete` action in the cutover and are
out of scope here.

Decision: no separate `error` detail field on `FormActionResult`. Today's shim
formats the caught exception into its error message; the core does not need to
persist that string because the cutover writes only `{id, reason}` to the
skipped blob and relies on Sentry for exception detail. If the shim needs the
exception text to reproduce today's message exactly, it catches/formats it at
the shim layer. (Revisit during implementation if this proves awkward.)

## Intentional behavior change: wrong-domain → `not_found`

Today `archive_or_restore_forms` produces two distinct failure messages:

- `"Could not find XForm {form_id}"` — id not found at all.
- `"XForm {form_id} does not belong to domain {domain}"` — found, wrong domain.

The new core scopes its lookup to the domain, so a cross-domain id is simply
absent and reports `reason='not_found'` — indistinguishable from a genuinely
missing id. This matches the target API security posture (no cross-domain
existence leak) described in the epic spec.

This is the **only** intended behavior change. In the existing UI flow, form
ids come from the user's own Manage Forms selection within their domain, so
the wrong-domain branch is effectively dead there; the change is safe in
practice. It is made explicit and reviewable: the characterization test for
the wrong-domain case is written against today's behavior first, then updated
deliberately in the refactor commit.

## Testing strategy

Two layers, written in this order:

1. **Characterization tests on `archive_or_restore_forms`** — written *first*,
   asserting today's `{"messages": {...}}` output (success messages, success
   count message, "could not find", and the soon-to-change wrong-domain
   message). Confirm green against current code, then refactor underneath
   them. Most of these are temporary (the shim is deleted at cutover) but they
   guarantee the extraction preserves behavior. Exactly one assertion (the
   wrong-domain message) is updated deliberately as part of the refactor.

2. **Unit tests on `iter_form_action_results`** — the lasting coverage the
   ticket asks for. Pure function, so cover edge cases directly: empty
   `form_ids`; all-found / all-missing / mixed; duplicate ids; cross-domain id
   → `not_found`; `action_fn` raising → `unexpected_error`; success path.

3. **Unit tests on the blob helpers** — round-trip write→read for both the
   `requested_ids` and `skipped_ids` payloads.

## Out of scope

- Any view (`XFormManagementView`), worker (`bulk_form_management_async`), or
  poll-endpoint changes — those are the SAAS-19895 cutover.
- Creating `BulkAsyncJob` rows or wiring blob helpers into the live path.
- The `delete` action and tombstones (SAAS-19704 / cutover).
- The richer skip-reason taxonomy beyond `not_found` / `unexpected_error`.
- Any UI / JS / template changes.

## Commit structure

Following repo conventions (move/rename separate from logic change; logical
chunks):

1. Characterization tests for `archive_or_restore_forms` against current
   behavior (green on current code).
2. Blob helpers + their unit tests.
3. Extract `iter_form_action_results` core + its unit tests; re-implement
   `archive_or_restore_forms` as a shim over it; update the single
   wrong-domain assertion as the documented intentional change.
