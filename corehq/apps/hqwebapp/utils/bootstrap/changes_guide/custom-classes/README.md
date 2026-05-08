## HQ-custom CSS class decisions

When migrating templates from Bootstrap 3 to 5, you'll encounte HQ-custom CSS classes that aren't part of the standard `panel-*` / `card-*` rename spec (e.g. `panel-appmanager`, `panel-case-actions`). This folder records the migration decision for each such class so the treatment is consistent across templates.

Apply this principle when migrating any custom class:

> **Minimize stylesheet, keep color.** Drop position/layout rules from custom classes and replicate them with B5 utilities on the template (`d-flex`, `position-relative`, `position-absolute`, `gap-*`, `mb-*`, etc.). Keep color/border/background rules under the renamed class.

Decisions in this folder are **conventions** — apply them consistently the next time you see the class, even in a different template. Don't re-evaluate.

### Process for a new custom class

1. Look at the original B3 LESS rule (not just the migrated SCSS; LESS→SCSS migration may have lost or simplified rules).
2. Categorize each rule:
   - Color/border/background → **keep** (in SCSS, under new class name).
   - Position/layout/spacing → **drop**, replace with B5 utility classes on the template.
   - Nested rules referencing dead B3 classes (e.g. `.panel-heading` inside the custom class) → **drop**, B5 markup uses different class names.
3. Add a new `.card-*` rule (or appropriate B5-themed prefix) with only the kept rules. Leave the old `.panel-*` rule in the SCSS for now — module-view templates that still reference it shouldn't break.
4. Update the templates you're migrating to use the new class + B5 utilities for layout.
5. Add a per-class file in this folder with the decision.

### Index of decisions

- [`panel-appmanager`](panel-appmanager.md) → `card-modern-gray`
- [`panel-case-actions`](panel-case-actions.md) → `card-case-actions`
- [`panel-case-actions-actions`](panel-case-actions-actions.md) → drop entirely (use B5 utilities)
- [`card-title`](card-title.md) (and `card-title-nolink`) → drop the inner heading wrapper (`<h3 class="card-title">`, `<h4 class="card-title">`, etc.); add a downsized heading-size utility class to the card-header element (`h4`→`h5`, `h3`→`h4`). `card-title-nolink` drops away as a side effect.
