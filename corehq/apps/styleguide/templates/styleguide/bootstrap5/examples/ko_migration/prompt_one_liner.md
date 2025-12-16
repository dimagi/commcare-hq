You have never seen this project before. It is a Django + Bootstrap 5 app
that is migrating from Knockout.js to Alpine.js and HTMX.

- Alpine is for light, local UI state.
- HTMX is for server-driven interactions with HTML partials returned by Django.
- We have a helper mixin called `HqHtmxActionMixin` that routes HTMX requests to
  methods decorated with `@hq_hx_action`, called from templates via `hq-hx-action="..."`.

Please keep behavior identical, avoid redesigning the UI, and prefer small,
reviewable changes that follow these patterns.
