hqDefine("scheduling/js/conditional_alert_list", [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/assert_properties',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/bootstrap3/components.ko',    // pagination and search box widgets
], function (
    $,
    ko,
    _,
    assertProperties,
    initialPageData
) {
    var table = null;

    var rule = function (options) {
        var self = ko.mapping.fromJS(options);
        self.requestInProgress = ko.observable(false);

        self.init = function (options) {
            ko.mapping.fromJS(options, self);
            self.requestInProgress(false);
        };
        self.init(options);

        self.editUrl = ko.computed(function () {
            return initialPageData.reverse("edit_conditional_alert", self.id());
        });

        self.action = function (action, e) {
            $(e.currentTarget).disableButton();
            self.requestInProgress(true);
            $.ajax({
                url: '',
                type: 'post',
                dataType: 'json',
                data: {
                    action: action,
                    rule_id: self.id(),
                },
            })
                .done(function (result) {
                    $(e.currentTarget).enableButton();
                    self.requestInProgress(false);
                    self.init(result.rule);
                    if (action === 'restart') {
                        if (result.status === 'success') {
                            alert(gettext("This rule has been restarted."));
                        } else if (result.status === 'error') {
                            var text = gettext(
                                "Unable to restart rule. Rules can only be started every two hours and there are " +
                                "%s minute(s) remaining before this rule can be started again."
                            );
                            text = interpolate(text, [result.minutes_remaining]);
                            alert(text);
                        }
                    }
                });
        };

        self.remove = function (model, e) {
            if (confirm(gettext("Are you sure you want to remove this conditional message?"))) {
                self.action('delete', e);
            }
        };

        self.toggleStatus = function (model, e) {
            var action = self.active() ? "deactivate" : "activate";
            self.action(action, e);
        };

        self.restart = function (model, e) {
            var prompt = null;
            if (initialPageData.get("limit_rule_restarts")) {
                prompt = gettext(
                    "A rule should only be restarted when you believe it is stuck and is not progressing. " +
                    "You will only be able to restart this rule once every two hours. Restart this rule?"
                );
            } else {
                prompt = gettext(
                    "A rule should only be restarted when you believe it is stuck and is not progressing. " +
                    "Your user is able to restart as many times as you like, but restarting too many times without " +
                    "finishing can place a burden on the system. Restart this rule?"
                );
            }
            if (confirm(prompt)) {
                self.action('restart', e);
            }
        };

        return self;
    };

    var ruleList = function (options) {
        assertProperties.assert(options, ['refreshUrl']);
        var self = {};

        self.rules = ko.observableArray();

        self.itemsPerPage = ko.observable(25);
        self.totalItems = ko.observable();
        self.showPaginationSpinner = ko.observable(false);

        self.emptyTable = ko.computed(function () {
            return self.totalItems() === 0;
        });
        self.currentPage = ko.observable(1);
        self.query = ko.observable('');
        self.goToPage = function (page) {
            self.showPaginationSpinner(true);
            self.currentPage(page);
            $.ajax({
                url: options.refreshUrl,
                data: {
                    action: 'list_conditional_alerts',
                    page: page,
                    limit: self.itemsPerPage(),
                    query: self.query(),
                },
                success: function (data) {
                    self.showPaginationSpinner(false);
                    if (_.isString(data)) {
                        // stop polling if data is HTML (login or error page)
                        return;
                    }
                    self.rules(_.map(data.rules, function (r) { return rule(r); }));
                    self.totalItems(data.total);
                    self.reloadPageSoon();
                },
            });
        };

        self.onPaginationLoad = function () {
            self.goToPage(self.currentPage());
        };

        self.reloadPageSoon = function () {
            setTimeout(function () {
                self.goToPage(self.currentPage());
            }, 10000);
        };

        self.reloadPageSoon();
        return self;
    };

    $(function () {
        $("#conditional-alert-list").koApplyBindings(ruleList({
            refreshUrl: initialPageData.reverse("conditional_alert_list_refresh"),
        }));
    });
});
