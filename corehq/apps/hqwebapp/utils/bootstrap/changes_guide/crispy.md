This template uses crispy forms.

Please ensure the form looks good after migration, and refer to the
<a href="https://www.commcarehq.org/styleguide/b5/organisms/forms/#crispy-forms" target="_blank">crispy forms
section</a> of the style guide.

A few useful things to know about crispy forms in Bootstrap 5:

* As described in <a href="https://www.commcarehq.org/styleguide/b5/organisms/forms/#crispy-forms-simple"
target="_blank">this section of the style guide</a>, best practice is to use one of HQ's standard helper classes
for layout. Doing so means you can delete <code>form_class</code>, <code>label_class</code>,
<code>field_class</code>, and <code>offset_class</code> from the form itself. This allows us to change the layout
of crispy forms across HQ without needing to update each individual form.
* If you do need to troubleshoot Bootstrap issues with crispy forms, be aware that Dimagi maintains a <a
href="https://github.com/dimagi/crispy-bootstrap3to5" target="_blank">crispy-bootstrap3to5 </a> repo with
transitional templates. You may also need to troubleshoot in the crispy templates.
