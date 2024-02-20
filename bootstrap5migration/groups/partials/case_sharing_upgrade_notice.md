
Line 3:
  <div class="well well-sm">

- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
`well` has been dropped in favor of a new component `card`

We attempted a basic find-replace of css classes that have equivalents,
including classes we had to re-create.

However, there has been some restructuring to the `card` element itself that
might not be entirely translatable this way. Please review and adjust
accordingly.

See: https://getbootstrap.com/docs/5.3/components/card/

- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

-  <div class="well well-sm">
+  <div class="card well-sm">

RENAMES
  - renamed well to card

