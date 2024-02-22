The `modal` plugin has been restructured since the removal of jQuery.

There is now a new way of triggering modal events and interacting with modals in javascript.
For instance, if we wanted to hide a modal with id `#bugReport` before, we would now do the
following...

An EXAMPLE for how to apply this change is provided below.
Please see docs for further details.

previously
```
$('#bugReport').modal('hide');
```

now
```
const bugReportModal = new bootstrap.Modal($('#bugReport'));
bugReportModal.hide();
```

Hint: make sure to list `hqwebapp/js/bootstrap5_loader` as a js dependency in the file where
bootstrap is referenced.

Old docs: https://getbootstrap.com/docs/3.4/javascript/#modals
New docs: https://getbootstrap.com/docs/5.3/components/modal/#via-javascript
