/**
 * This provides the UI for a case detail tab's nodeset.
 *
 * It contains a dropdown where to select the type of data,
 * currently either a child case type or a custom xpath expression.
 */
hqDefine('app_manager/js/details/detail_tab_nodeset', function () {
    return function (options) {
        var self = {};

        self.nodeset = ko.observable(options.nodeset);
        self.nodesetCaseType = ko.observable(options.nodesetCaseType);
        self.nodesetFilter = ko.observable(options.nodesetFilter);

        self.dropdownOptions = [{name: gettext("Data Tab: Custom Expression"), value: ""}].concat(
            _.map(options.caseTypes, function (t) {
                return {name: gettext("Data Tab: Child Cases: ") + t, value: t};
            })
        );

        self.showXpath = ko.computed(function () {
            return !self.nodesetCaseType();
        });

        self.showFilter = ko.observable(!!self.nodesetFilter());    // show button if there's no saved filter

        self.ui = $(_.template($("#module-case-detail-tab-nodeset-template").text())());
        self.ui.koApplyBindings(self);

        hqImport("hqwebapp/js/bootstrap3/main").eventize(self);
        self.nodeset.subscribe(function () {
            self.fire('change');
        });
        self.nodesetCaseType.subscribe(function (newValue) {
            self.fire('change');
            if (newValue) {
                self.nodeset("");
            } else {
                self.nodesetFilter("");
                self.showFilter(false);
            }
        });
        self.nodesetFilter.subscribe(function () {
            self.fire('change');
        });

        return self;
    };
});
