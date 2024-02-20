
Line 40:
      <form class="well well-sm form-inline" method="post" action="{% url "add_group" domain %}" id="create_group_form">

- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
`form-inline` has been dropped. Use grid utilities instead.

- note that `<label>` elements now require `form-label` class

- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

      <form class="well well-sm form-inline" method="post" action="{% url "add_group" domain %}" id="create_group_form">

- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
`well` has been dropped in favor of a new component `card`

We attempted a basic find-replace of css classes that have equivalents,
including classes we had to re-create.

However, there has been some restructuring to the `card` element itself that
might not be entirely translatable this way. Please review and adjust
accordingly.

See: https://getbootstrap.com/docs/5.3/components/card/

- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

-      <form class="well well-sm form-inline" method="post" action="{% url "add_group" domain %}" id="create_group_form">
+      <form class="card well-sm form-inline" method="post" action="{% url "add_group" domain %}" id="create_group_form">

RENAMES
  - renamed well to card


Line 50:
    <div class="panel panel-default">

- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
`panel` has been dropped in favor of a new component `card`

We attempted a basic find-replace of css classes that have equivalents,
including classes we had to re-create.

However, there has been some restructuring to the `card` element itself that
might not be entirely translatable this way. Please review and adjust
accordingly.

See: https://getbootstrap.com/docs/5.3/components/card/

- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

-    <div class="panel panel-default">
+    <div class="card card-default">

RENAMES
  - renamed panel-default to card-default
   - renamed panel to card


Line 51:
-      <div class="panel-heading">
+      <div class="card-header">

RENAMES
  - renamed panel-heading to card-header


Line 52:
-        <h3 class="panel-title">{% trans "Project Groups" %}</h3>
+        <h3 class="card-title">{% trans "Project Groups" %}</h3>

RENAMES
  - renamed panel-title to card-title


Line 54:
-      <div class="panel-body">
+      <div class="card-body">

RENAMES
  - renamed panel-body to card-body


Line 98:
-                      <span class="js-case-sharing-alert label label-warning"
+                      <span class="js-case-sharing-alert badge text-bg-warning"

RENAMES
  - renamed label to badge
   - renamed label-warning to text-bg-warning

