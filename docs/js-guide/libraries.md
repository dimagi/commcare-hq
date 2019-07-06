# Third-Party Libraries

[jQuery](https://jquery.com/) is available throughout HQ. We use jQuery 3 everywhere except in Web Apps, which depends on [marionette](https://marionettejs.com/) v2, which is only compatible with jQuery 2.

[Underscore](http://underscorejs.org/) is available throughout HQ for utilities.

[Knockout](http://knockoutjs.com/) is also available throughout HQ and should be used for new code. We use Knockout 3.0.

[Backbone](http://backbonejs.org/) is used in Web Apps. It **should not** be used outside of Web Apps.

[Angular](https://angularjs.org/) is used only in custom reports for ICDS. It **should not** be used for new code. The angular we do have is Angular 1, which is outdated but is effectively a different framework than later versions of angular, making upgrading non-trivial. It's [unclear](https://toddmotto.com/future-of-angular-1-x#whats-next-for-angular-1x) how long Angular 1 will be supported by its creators.

We use [bower](https://bower.io/) for package management, so new libraries should be added to [bower.json](https://github.com/dimagi/commcare-hq/blob/master/bower.json).
