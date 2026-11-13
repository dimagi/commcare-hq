Task:

Help me migrate this Knockout-driven UI to a server-driven pattern using HTMX,
with Alpine.js used only for small UI state (like inline-edit toggles).

Project context:

- Django + Bootstrap 5 app.
- HTMX is available and we prefer HTML responses over JSON.
- In this codebase we use a helper mixin, `HqHtmxActionMixin`, which:
  - Is mixed into Django class-based views.
  - Routes HTMX requests based on a custom header (e.g. `HQ-HX-Action`) to methods
    decorated with `@hq_hx_action("get" | "post")`.
  - In templates, we add `hq-hx-action="method_name"` to elements, alongside
    `hx-get`/`hx-post` pointing at the view URL.

Goals:

- Move long-lived or business-critical state and validation into Django, using HTMX.
- Use Alpine only for local UI state (e.g. `isEditing`, `isSubmitting`, toggles, etc.).
- Replace Knockout bindings with:
  - HTMX calls to server-side actions for data changes.
  - Alpine for small interactive pieces that don't need server involvement.

Constraints:

- Keep user-visible behavior the same (no UX redesign).
- Suggest a small set of HTMX actions (e.g. `load_items`, `add_item`, `update_item`, `delete_item`).
- Use common HTMX attributes: `hx-get`, `hx-post`, `hx-target`, `hx-swap`, `hx-trigger`,
  and `hx-disabled-elt`.
- When inputs don't need new HTML on every change, consider using `hx-swap="none"` and a
  “no content” response pattern.

Output:

1. A sketch of a Django view class using `HqHtmxActionMixin` with a few `@hq_hx_action` methods.
2. A main template snippet showing a container that loads a partial with HTMX.
3. A partial template snippet wiring forms/inputs/buttons to those HTMX actions.
4. Any small Alpine snippets needed for purely UI concerns.

Existing Knockout template + JS to migrate:

<paste KO code here>
