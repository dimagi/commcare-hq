# Third-Party Libraries

- jQuery: Available throughout HQ. We use jQuery 2 ([2.2.0](https://github.com/dimagi/commcare-hq/blob/master/bower.json)) but are in the process of migrating to jQuery 3.0, which has a number of breaking changes. What does this mean for you?
  - Check out the [migration guide](https://jquery.com/upgrade-guide/3.0), or just skim the [commcare-hq migration branch's commits](https://github.com/dimagi/commcare-hq/compare/jquery-3-1-0) to see the patterns most commonly used in HQ that need to be updated. 
  - Avoid constructs that are will break in 3+
  - For now, also avoid constructs that are only available in 3+
- Knockout: available throughout HQ. Should be on Knockout 3.0, although there are a few places that haven't yet been upgraded from 2.x.
- Backbone: Used in CloudCare. Prefer Knockout for new code.
- Angular: Used in a few places (dashboards, exports, app summaries). Prefer Knockout for new code.
