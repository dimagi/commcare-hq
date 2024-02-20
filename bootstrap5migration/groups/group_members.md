
Line 55:
-             class="btn btn-default"
+             class="btn btn-outline-primary"

RENAMES
  - renamed btn-default to btn-outline-primary


Line 56:
-             data-toggle="modal">
+             data-bs-toggle="modal">

RENAMES
  - renamed data-toggle to data-bs-toggle


Line 62:
-             class="btn btn-default"
+             class="btn btn-outline-primary"

RENAMES
  - renamed btn-default to btn-outline-primary


Line 63:
-             data-toggle="modal">
+             data-bs-toggle="modal">

RENAMES
  - renamed data-toggle to data-bs-toggle


Line 68:
-        <a class="btn btn-danger pull-right" style="margin-right: 45px;" data-toggle="modal" href="#delete_group_modal">
+        <a class="btn btn-outline-danger float-end" style="margin-right: 45px;" data-bs-toggle="modal" href="#delete_group_modal">

RENAMES
  - renamed pull-right to float-end
   - renamed btn-danger to btn-outline-danger
   - renamed data-toggle to data-bs-toggle


Line 77:
                class="form-inline"

- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
`form-inline` has been dropped. Use grid utilities instead.

- note that `<label>` elements now require `form-label` class

- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


Line 85:
-                    class="btn btn-default verify-button">
+                    class="btn btn-outline-primary verify-button">

RENAMES
  - renamed btn-default to btn-outline-primary


Line 106:
    <ul class="nav nav-tabs sticky-tabs" role="tablist" style="margin-bottom: 20px;">

- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
The `nav` element has been restructured a bit so that you need to explicitly label
child elements with `nav-item` and `nav-link`.

An EXAMPLE for how to apply this change is provided below.
Please see docs for further details.

Previously:
```
<ul class="nav nav-tabs">
    <li class="active">
        <a href="#">Home</a>
    </li>
    <li>
        <a href="#">Profile</a>
    </li>
    <li>
        <a href="#">Messages</a>
    </li>
</ul>
```

Now:
```
<ul class="nav nav-tabs">
    <li class="nav-item active">
        <a class="nav-link active" aria-current="page" href="#">Home</a>
    </li>
    <li class="nav-item">
        <a class="nav-link" href="#">Profile</a>
    </li>
    <li class="nav-item">
        <a class="nav-link" href="#">Messages</a>
    </li>
</ul>
```

See: https://getbootstrap.com/docs/5.3/components/navs-tabs/#base-nav

- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


Line 108:
-        <a href="#membership-tab" aria-controls="home" role="tab" data-toggle="tab">
+        <a href="#membership-tab" aria-controls="home" role="tab" data-bs-toggle="tab">

RENAMES
  - renamed data-toggle to data-bs-toggle


Line 113:
-        <a href="#groupdata-tab" aria-controls="profile" role="tab" data-toggle="tab">
+        <a href="#groupdata-tab" aria-controls="profile" role="tab" data-bs-toggle="tab">

RENAMES
  - renamed data-toggle to data-bs-toggle


Line 122:
-        <div class="panel-body">
+        <div class="card-body">

RENAMES
  - renamed panel-body to card-body


Line 128:
              <div class="form-group">

- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
`form-group` has been dropped. Use grid utilities instead.

Since we are opting for vertical forms (where the label is directly above the field),
the replacement for `form-group` is most likely just `mb-3` and the child `div` with a column
class surrounding the `form-control` element can be removed, along with the column class that
appears with the `<label>` `class` attribute. Most often, the `<label>` `class` only needs to
contain the `form-label` class now.

- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


Line 129:
-                <label class="control-label col-xs-12 col-sm-4 col-md-4 col-lg-2">
+                <label class="form-label col-sm-12 col-md-4 col-lg-4 col-xl-2">

RENAMES
  - renamed control-label to form-label
   - renamed col-lg-<num> to col-xl-<num>
   - renamed col-md-<num> to col-lg-<num>
   - renamed col-sm-<num> to col-md-<num>
   - renamed col-xs-<num> to col-sm-<num>


Line 132:
-                <div class="col-xs-12 col-sm-8 col-md-8 col-lg-6 controls-text">
+                <div class="col-sm-12 col-md-8 col-lg-8 col-xl-6 controls-text">

RENAMES
  - renamed col-lg-<num> to col-xl-<num>
   - renamed col-md-<num> to col-lg-<num>
   - renamed col-sm-<num> to col-md-<num>
   - renamed col-xs-<num> to col-sm-<num>


Line 159:
-              <div class="col-sm-12">
+              <div class="col-md-12">

RENAMES
  - renamed col-sm-<num> to col-md-<num>


Line 178:
-        <div class="panel-body">
+        <div class="card-body">

RENAMES
  - renamed panel-body to card-body


Line 184:
              <div class="form-group">

- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
`form-group` has been dropped. Use grid utilities instead.

Since we are opting for vertical forms (where the label is directly above the field),
the replacement for `form-group` is most likely just `mb-3` and the child `div` with a column
class surrounding the `form-control` element can be removed, along with the column class that
appears with the `<label>` `class` attribute. Most often, the `<label>` `class` only needs to
contain the `form-label` class now.

- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


Line 185:
-                <label class="control-label col-xs-12 col-sm-4 col-md-4 col-lg-2">
+                <label class="form-label col-sm-12 col-md-4 col-lg-4 col-xl-2">

RENAMES
  - renamed control-label to form-label
   - renamed col-lg-<num> to col-xl-<num>
   - renamed col-md-<num> to col-lg-<num>
   - renamed col-sm-<num> to col-md-<num>
   - renamed col-xs-<num> to col-sm-<num>


Line 188:
-                <div class="controls-text col-xs-12 col-sm-8 col-md-8 col-lg-6">
+                <div class="controls-text col-sm-12 col-md-8 col-lg-8 col-xl-6">

RENAMES
  - renamed col-lg-<num> to col-xl-<num>
   - renamed col-md-<num> to col-lg-<num>
   - renamed col-sm-<num> to col-md-<num>
   - renamed col-xs-<num> to col-sm-<num>


Line 211:
                <div class="form-group">

- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
`form-group` has been dropped. Use grid utilities instead.

Since we are opting for vertical forms (where the label is directly above the field),
the replacement for `form-group` is most likely just `mb-3` and the child `div` with a column
class surrounding the `form-control` element can be removed, along with the column class that
appears with the `<label>` `class` attribute. Most often, the `<label>` `class` only needs to
contain the `form-label` class now.

- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


Line 212:
-                  <label class="control-label col-sm-2">
+                  <label class="form-label col-md-2">

RENAMES
  - renamed control-label to form-label
   - renamed col-sm-<num> to col-md-<num>


Line 215:
-                  <div class="col-sm-9">
+                  <div class="col-md-9">

RENAMES
  - renamed col-sm-<num> to col-md-<num>


Line 221:
-                  <div class="col-sm-9 col-sm-offset-2">
+                  <div class="col-md-9 col-sm-offset-2">

RENAMES
  - renamed col-sm-<num> to col-md-<num>


Line 241:
          <div class="modal-header">

- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
The `modal` component was rewritten and now the close button should come after
the `modal-title`. Also, there is a new accessibility attribute `aria-labelledby`
which you can add to label the modal with the title. See documentation for details...

An EXAMPLE for how to apply this change is provided below.
Please see docs for further details.

Previously:
```
<div class="modal-header">
    <button type="button" class="close" data-dismiss="modal" aria-label="Close"><span aria-hidden="true">&times;</span></button>
    <h4 class="modal-title">Modal title</h4>
</div>
```

Now:
```
<div class="modal-header">
    <h4 class="modal-title" id="exampleModalLabel">Modal title</h4>
    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
</div>
```

See: Styleguide (B5) > Molecules > Modals for full example
Official Docs: https://getbootstrap.com/docs/5.3/components/modal/

- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


Line 242:
            <button type="button" class="close" data-dismiss="modal" aria-label="Close"><span aria-hidden="true">&times;</span></button>

- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
`close` has been renamed to `btn-close` (which we've automatically handled)

However, `&times;` in the HTML is no longer needed, as an embedded SVG is now used instead.
You can remove this.

An EXAMPLE for how to apply this change is provided below.

Previously:
```
<button type="button" class="close" data-dismiss="modal"><span aria-hidden="true">&times;</span></button>
```

Now:
```
<button type="button" class="btn-close" aria-label="Close"></button>
```

- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

-            <button type="button" class="close" data-dismiss="modal" aria-label="Close"><span aria-hidden="true">&times;</span></button>
+            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"><span aria-hidden="true">&times;</span></button>

RENAMES
  - renamed close to btn-close
   - renamed data-dismiss to data-bs-dismiss


Line 259:
-              <a href="#" data-dismiss="modal" class="btn btn-default">{% trans 'Cancel' %}</a>
+              <a href="#" data-bs-dismiss="modal" class="btn btn-outline-primary">{% trans 'Cancel' %}</a>

RENAMES
  - renamed btn-default to btn-outline-primary
   - renamed data-dismiss to data-bs-dismiss


Line 260:
-              <button class="btn btn-danger disable-on-submit" type="submit">
+              <button class="btn btn-outline-danger disable-on-submit" type="submit">

RENAMES
  - renamed btn-danger to btn-outline-danger


Line 273:
          <div class="modal-header">

- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
The `modal` component was rewritten and now the close button should come after
the `modal-title`. Also, there is a new accessibility attribute `aria-labelledby`
which you can add to label the modal with the title. See documentation for details...

An EXAMPLE for how to apply this change is provided below.
Please see docs for further details.

Previously:
```
<div class="modal-header">
    <button type="button" class="close" data-dismiss="modal" aria-label="Close"><span aria-hidden="true">&times;</span></button>
    <h4 class="modal-title">Modal title</h4>
</div>
```

Now:
```
<div class="modal-header">
    <h4 class="modal-title" id="exampleModalLabel">Modal title</h4>
    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
</div>
```

See: Styleguide (B5) > Molecules > Modals for full example
Official Docs: https://getbootstrap.com/docs/5.3/components/modal/

- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


Line 274:
            <button type="button" class="close" data-dismiss="modal" aria-label="Close"><span aria-hidden="true">&times;</span></button>

- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
`close` has been renamed to `btn-close` (which we've automatically handled)

However, `&times;` in the HTML is no longer needed, as an embedded SVG is now used instead.
You can remove this.

An EXAMPLE for how to apply this change is provided below.

Previously:
```
<button type="button" class="close" data-dismiss="modal"><span aria-hidden="true">&times;</span></button>
```

Now:
```
<button type="button" class="btn-close" aria-label="Close"></button>
```

- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

-            <button type="button" class="close" data-dismiss="modal" aria-label="Close"><span aria-hidden="true">&times;</span></button>
+            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"><span aria-hidden="true">&times;</span></button>

RENAMES
  - renamed close to btn-close
   - renamed data-dismiss to data-bs-dismiss


Line 284:
              <div class="form-group">

- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
`form-group` has been dropped. Use grid utilities instead.

Since we are opting for vertical forms (where the label is directly above the field),
the replacement for `form-group` is most likely just `mb-3` and the child `div` with a column
class surrounding the `form-control` element can be removed, along with the column class that
appears with the `<label>` `class` attribute. Most often, the `<label>` `class` only needs to
contain the `form-label` class now.

- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


Line 285:
-                <label class="control-label col-sm-3" for="group-name-input">{% trans "Group Name" %}</label>
+                <label class="form-label col-md-3" for="group-name-input">{% trans "Group Name" %}</label>

RENAMES
  - renamed control-label to form-label
   - renamed col-sm-<num> to col-md-<num>


Line 286:
-                <div class="col-sm-9">
+                <div class="col-md-9">

RENAMES
  - renamed col-sm-<num> to col-md-<num>


Line 290:
              <div class="form-group">

- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
`form-group` has been dropped. Use grid utilities instead.

Since we are opting for vertical forms (where the label is directly above the field),
the replacement for `form-group` is most likely just `mb-3` and the child `div` with a column
class surrounding the `form-control` element can be removed, along with the column class that
appears with the `<label>` `class` attribute. Most often, the `<label>` `class` only needs to
contain the `form-label` class now.

- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


Line 291:
-                <label class="control-label col-sm-3" for="group-case-sharing-input">{% trans "Case Sharing" %}</label>
+                <label class="form-label col-md-3" for="group-case-sharing-input">{% trans "Case Sharing" %}</label>

RENAMES
  - renamed control-label to form-label
   - renamed col-sm-<num> to col-md-<num>


Line 292:
-                <div class="col-sm-9">
+                <div class="col-md-9">

RENAMES
  - renamed col-sm-<num> to col-md-<num>


Line 317:
              <div class="form-group">

- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
`form-group` has been dropped. Use grid utilities instead.

Since we are opting for vertical forms (where the label is directly above the field),
the replacement for `form-group` is most likely just `mb-3` and the child `div` with a column
class surrounding the `form-control` element can be removed, along with the column class that
appears with the `<label>` `class` attribute. Most often, the `<label>` `class` only needs to
contain the `form-label` class now.

- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


Line 318:
-                <label class="control-label col-sm-3" for="group-reporting-input">{% trans "Reporting" %}</label>
+                <label class="form-label col-md-3" for="group-reporting-input">{% trans "Reporting" %}</label>

RENAMES
  - renamed control-label to form-label
   - renamed col-sm-<num> to col-md-<num>


Line 319:
-                <div class="col-sm-6">
+                <div class="col-md-6">

RENAMES
  - renamed col-sm-<num> to col-md-<num>


Line 335:
-              <a href="#" class="btn btn-default" data-dismiss="modal">{% trans "Cancel" %}</a>
+              <a href="#" class="btn btn-outline-primary" data-bs-dismiss="modal">{% trans "Cancel" %}</a>

RENAMES
  - renamed btn-default to btn-outline-primary
   - renamed data-dismiss to data-bs-dismiss


Line 349:
          <div class="modal-header">

- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
The `modal` component was rewritten and now the close button should come after
the `modal-title`. Also, there is a new accessibility attribute `aria-labelledby`
which you can add to label the modal with the title. See documentation for details...

An EXAMPLE for how to apply this change is provided below.
Please see docs for further details.

Previously:
```
<div class="modal-header">
    <button type="button" class="close" data-dismiss="modal" aria-label="Close"><span aria-hidden="true">&times;</span></button>
    <h4 class="modal-title">Modal title</h4>
</div>
```

Now:
```
<div class="modal-header">
    <h4 class="modal-title" id="exampleModalLabel">Modal title</h4>
    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
</div>
```

See: Styleguide (B5) > Molecules > Modals for full example
Official Docs: https://getbootstrap.com/docs/5.3/components/modal/

- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


Line 350:
            <button type="button" class="close" data-dismiss="modal" aria-label="Close"><span aria-hidden="true">&times;</span></button>

- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
`close` has been renamed to `btn-close` (which we've automatically handled)

However, `&times;` in the HTML is no longer needed, as an embedded SVG is now used instead.
You can remove this.

An EXAMPLE for how to apply this change is provided below.

Previously:
```
<button type="button" class="close" data-dismiss="modal"><span aria-hidden="true">&times;</span></button>
```

Now:
```
<button type="button" class="btn-close" aria-label="Close"></button>
```

- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

-            <button type="button" class="close" data-dismiss="modal" aria-label="Close"><span aria-hidden="true">&times;</span></button>
+            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"><span aria-hidden="true">&times;</span></button>

RENAMES
  - renamed close to btn-close
   - renamed data-dismiss to data-bs-dismiss


Line 379:
-              <a href="#" class="btn btn-default" data-dismiss="modal">{% trans "Cancel" %}</a>
+              <a href="#" class="btn btn-outline-primary" data-bs-dismiss="modal">{% trans "Cancel" %}</a>

RENAMES
  - renamed btn-default to btn-outline-primary
   - renamed data-dismiss to data-bs-dismiss

