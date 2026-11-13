Task:

Translate this Knockout-based widget into Alpine.js, using inline Alpine in the template.

Assume the following about the project:

- It's a Django + Bootstrap 5 app.
- Alpine.js is already loaded globally on the page.
- We are slowly migrating away from Knockout.js, but we don't want to change server-side code.

Constraints:

- Keep the HTML structure, CSS classes, and behavior the same for the user.
- Replace Knockout `data-bind` attributes with Alpine attributes like `x-model`, `x-text`,
  `x-show`, `x-for`, and small methods declared in `x-data`.
- Do NOT create a separate JavaScript file for this example; keep Alpine inline, e.g.:

  <div x-data="{ ... }">...</div>

- Do NOT change Django template tags or server-side logic.

Output:

1. The updated HTML snippet using Alpine.
2. A brief explanation (1-3 bullet points) of what you changed and why.

Code to migrate (Knockout template + JS):

<paste Knockout code here>
