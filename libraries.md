# Third-Party Libraries

- jQuery: Available throughout HQ. We use ([jQuery 3](https://github.com/dimagi/commcare-hq/blob/master/bower.json)) everywhere except in Web Apps, which depends on [marionette](https://marionettejs.com/) v2, which is only compatible with jQuery 2.
- Knockout: available throughout HQ. Should be on Knockout 3.0, although there are a few places that haven't yet been upgraded from 2.x.
- Backbone: Used in CloudCare. Prefer Knockout for new code.
- Angular: Used in a few places (dashboards, exports, app summaries). Prefer Knockout for new code.
