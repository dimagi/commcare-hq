Context about this project and what I'm doing:

- This code is from a large Django + Bootstrap 5 web app.
- Historically it used Knockout.js for client-side view models.
- We are now migrating to:
  - Alpine.js for lightweight interactivity and small, local UI state, and
  - HTMX for server-coordinated interactions, where Django renders HTML partials.

High-level goals:

- Reduce JavaScript complexity and avoid duplicating server-side logic in the browser.
- Rely on Django templates for most HTML and layout.
- Use Alpine for light, local interactivity and UI-only state.
- Use HTMX for forms, tables, filtering, pagination, and other server-backed actions.

Codebase-specific detail:

- We have a helper mixin called `HqHtmxActionMixin` in our codebase.
- It's a Django class-based-view mixin that:
  - Reads a custom request header like `HQ-HX-Action`.
  - Routes the request to a method on the view whose name matches that action.
  - Those methods are decorated with `@hq_hx_action("get" | "post" | "any_method")`.
  - In templates, we call them via `hq-hx-action="method_name"` together with `hx-get`/`hx-post`.
- You don't need to change the internals of `HqHtmxActionMixin`; just use it in examples.

<note: if you can, include the htmx_action.py file for reference>

Important constraints:

- Preserve existing behavior and user-facing semantics.
- Don't redesign the UI, just translate bindings / models.
- Keep diffs small and reviewable.
- Keep Django template logic and context variables intact where possible.

I'll paste Knockout JS and related templates next. Please work within this context.
