Task:

Convert this Knockout view model into a reusable Alpine.js component defined in a separate JS module.

Project context (so you don't have to guess):

- Django + Bootstrap 5 app.
- Alpine.js is our main front-end library for local UI state.
- Initial values can be passed from the server via a global `initialPageData` helper or
  similar mechanism.

Constraints:

- Preserve the behavior of the existing Knockout model (same fields, defaults, and events).
- Define the Alpine model as a function that returns a data object, e.g.:

  export default (initialValue) => ({
      // properties and methods here
  });

- Show how to register it in a JS entry file with:

  import Alpine from "alpinejs";
  import myModel from "path/to/module";

  Alpine.data("myModelName", () => myModel(initialValue));
  Alpine.start();

- Do NOT change backend logic or Django context variables.

Output:

1. A JS module exporting the Alpine model (`export default (initial) => ({ ... })`).
2. A JS entry file snippet that imports it, registers `Alpine.data`, and calls `Alpine.start()`.
3. If needed, an example HTML snippet showing `x-data="myModelName(...)"`.

Existing Knockout code to migrate:

<paste KO model + relevant HTML here, or reference files>
