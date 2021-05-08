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

        self.dropdownOptions = _.map(options.caseTypes, function (t) {
            return {name: gettext("Data Tab: Child Cases: ") + t, value: t};
        }).concat([{name: gettext("Data Tab: Custom Expression"), value: ""}]);

        self.dropdownValue = ko.observable(_.find(self.dropdownOptions, function (o) {
            return o.value === options.nodesetCaseType;
        }));
        self.dropdownValue.subscribe(function (newValue) {
            if (!newValue.value) {
                self.nodeset("");
            }
        });

        self.showXpath = ko.computed(function () {
            return !self.dropdownValue().value;
        });

        var ui = '<select class="form-control" data-bind="options: dropdownOptions, optionsText: \'name\', value: dropdownValue"></select>';
        ui += '<textarea type="text" class="form-control" data-bind="value: nodeset, visible: showXpath" style="margin-top: 5px" /></textarea>';
        if (hqImport('hqwebapp/js/toggles').toggleEnabled('SYNC_SEARCH_CASE_CLAIM')) {
            ui += '<p data-bind="visible: showXpath() && nodeset()" class="help-block">' + gettext("This data will not be shown for case search results.") + '</p>';
        }
        self.ui = $('<div>' + ui + '</div>');
        self.ui.koApplyBindings(self);

        hqImport("hqwebapp/js/main").eventize(self);
        self.nodeset.subscribe(function () {
            self.fire('change');
        });
        self.dropdownValue.subscribe(function () {
            self.fire('change');
        });

        return self;
    };
});
