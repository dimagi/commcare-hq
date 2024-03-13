hqDefine("data_interfaces/js/auto_update_rules", [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/initial_page_data',
    'analytix/js/google',
    'hqwebapp/js/bootstrap3/components.ko', // for pagination and search box
], function (
    $,
    ko,
    _,
    initialPageData,
    googleAnalytics
) {

    var RuleViewModel = function (data, parent) {
        ko.mapping.fromJS(data, {}, this);

        this.url = ko.pureComputed(function () {
            if (!this.upstream_id()) {
                return data.edit_url;
            }

            return parent.unlockLinkedData() ? data.edit_url : data.view_url;
        }, this);
    };

    var RuleListViewModel = function (rules) {
        var self = {};

        self.has_linked_data = initialPageData.get('has_linked_data');
        self.allowEdit = initialPageData.get('can_edit_linked_data');
        self.unlockLinkedData = ko.observable(false);

        self.toggleLinkedLock = function () {
            self.unlockLinkedData(!self.unlockLinkedData());
        };

        self.rules = ko.observableArray(rules.map(rule => new RuleViewModel(rule, self)));
        self.paginatedRules = ko.observableArray([]);
        self.rulesById = ko.computed(function () {
            return _.indexBy(self.rules(), 'id');
        });

        self.hasLinkedModels = ko.pureComputed(function () {
            return self.rules().some(rule => rule.upstream_id());
        });

        // pagination
        self.itemsPerPage = ko.observable(5);
        self.totalItems = ko.computed(function () {
            return self.rules().length;
        });
        self.currentPage = 1;

        self.goToPage = function (page) {
            self.currentPage = page;
            self.paginatedRules.removeAll();
            var skip = (self.currentPage - 1) * self.itemsPerPage();
            self.paginatedRules(self.rules().slice(skip, skip + self.itemsPerPage()));
        };

        self.onPaginationLoad = function () {
            self.goToPage(1);
        };

        // actions
        self.deleteRule = function (rule) {
            $.ajax({
                url: "",
                type: "POST",
                dataType: 'json',
                data: {
                    action: 'delete',
                    id: rule.id,
                },
                success: function (data) {
                    if (data.success) {
                        self.rules.remove(rule);
                        self.goToPage(1);
                    } else {
                        self.showActionError(rule, data.error);
                    }
                },
                error: function () {
                    self.showActionError(rule, gettext("Issue communicating with server. Try again."));
                },
            });
        };

        self.updateRule = function (action, rule) {
            $.ajax({
                url: "",
                type: "POST",
                dataType: 'json',
                data: {
                    action: action,
                    id: rule.id,
                },
                success: function (data) {
                    if (data.success) {
                        self.rules.remove(rule);
                        var updatedRule = new RuleViewModel(data.itemData, self);
                        self.rules.push(updatedRule);
                        self.rules(_.sortBy(self.rules(), function (rule) { return rule.name().toUpperCase(); }));
                        self.goToPage(1);
                    } else {
                        self.showActionError(rule, data.error);
                    }
                },
                error: function () {
                    self.showActionError(rule, gettext("Issue communicating with server. Try again."));
                },
            });
        };

        self.showActionError = function (rule, error) {
            var ruleToUpdate = self.rulesById()[rule.id];
            ruleToUpdate.action_error = error;
            self.rules.valueHasMutated();
        };

        self.modalModel = ko.observable();
        self.setModalModel = function (model) {
            self.modalModel(model);
        };

        return self;
    };

    var RuleRunHistoryViewModel = function (ruleRuns) {
        var self = {};
        self.ruleRuns = ko.mapping.fromJS(ruleRuns);
        self.paginatedRuleRuns = ko.observableArray([]);

        // search box
        self.caseTypeQuery = ko.observable();
        self.filteredRuleRuns = ko.observableArray([]);
        self.matchesQuery = function (ruleRun) {
            return !self.caseTypeQuery() || ruleRun.case_type().toLowerCase().indexOf(self.caseTypeQuery().toLowerCase()) !== -1;
        };
        self.filter = function () {
            self.filteredRuleRuns(_.filter(self.ruleRuns(), self.matchesQuery));
            self.goToPage(1);
        };

        // pagination
        self.itemsPerPage = ko.observable(25);
        self.totalItems = ko.computed(function () {
            return self.caseTypeQuery() ? self.filteredRuleRuns().length : self.ruleRuns().length;
        });
        self.currentPage = 1;

        self.goToPage = function (page) {
            self.currentPage = page;
            self.paginatedRuleRuns.removeAll();
            var skip = (self.currentPage - 1) * self.itemsPerPage();
            var visibleRuleRuns = self.caseTypeQuery() ? self.filteredRuleRuns() : self.ruleRuns();
            self.paginatedRuleRuns(visibleRuleRuns.slice(skip, skip + self.itemsPerPage()));
        };

        self.onPaginationLoad = function () {
            self.goToPage(1);
        };
        return self;
    };

    $(function () {
        var rules = initialPageData.get('rules');
        var ruleListViewModel = RuleListViewModel(rules);
        $("#ko-tabs-update-rules").koApplyBindings(ruleListViewModel);
        $("#edit-warning-modal").koApplyBindings(ruleListViewModel);

        var ruleRuns = initialPageData.get('rule_runs');
        var ruleRunHistoryViewModel = RuleRunHistoryViewModel(ruleRuns);
        $("#ko-tabs-rule-run-history").koApplyBindings(ruleRunHistoryViewModel);

        $("#add-new").click(function () {
            googleAnalytics.track.event('Automatic Case Closure', 'Rules', 'Set Rule');
        });
    });
});
