This template uses inline styles. Please revisit this usage.

Inline styles are not best practice. While replacing them is not strictly necessary for this migration,
Bootstrap 5 includes a host of utility classes that can replace a lot of the imline style usage in HQ.

Some common replacements:
* Display styles like `display: none` can be replaced with classes like `d-none`. See https://getbootstrap.com/docs/5.0/utilities/display/
* Spacing styles like `margin-bottom: 10px` can be replaced with classes like `mb-3`. See https://getbootstrap.com/docs/5.0/utilities/spacing/
* Text alignment styles like `text-align: right` can be replaced with classes like `text-end`. See https://getbootstrap.com/docs/5.0/utilities/text/
* Usages of the `em` unit should be updated to use the `rem` unit
* Layouts achieved using inline styling can sometimes be replaced with usage of flex. See https://getbootstrap.com/docs/5.0/utilities/flex/

See all of Bootstrap 5's utility classes: https://getbootstrap.com/docs/5.0/utilities/

For styles that can't be replaced with utility classes, page-specific styles go in Sass files under `hqwebapp`. An example is [this file](https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/hqwebapp/static/cloudcare/scss/formplayer-common/query.scss) for styles specific to the Web Apps search screen.
