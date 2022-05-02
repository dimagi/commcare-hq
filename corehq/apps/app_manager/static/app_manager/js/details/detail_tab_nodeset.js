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

        self.showFilter = ko.observable(!!self.nodesetFilter());

        var ui = '<select class="form-control" data-bind="options: dropdownOptions, optionsText: \'name\', optionsValue: \'value\', value: nodesetCaseType" style="margin-bottom: 5px;"></select>';
        ui += '<button class="btn btn-default btn-xs" data-bind="visible: !showFilter() && !showXpath(), click: function () { showFilter(true); }">'
        ui += '<i class="fa fa-plus"></i>' + gettext("Add filter");
        ui += '</button>';
        ui += '<input type="text" class="form-control" data-bind="value: nodesetFilter, visible: showFilter" placeholder="' + gettext("referral = 'y'") + '" />';
        ui += '<textarea class="form-control" data-bind="value: nodeset, visible: showXpath" /></textarea>';
        if (hqImport('hqwebapp/js/toggles').toggleEnabled('SYNC_SEARCH_CASE_CLAIM')) {
            ui += '<p data-bind="visible: showXpath() && nodeset()" class="help-block">' + gettext("This data will not be shown for case search results.") + '</p>';
        }
        self.ui = $('<div>' + ui + '</div>');
        self.ui.koApplyBindings(self);

        hqImport("hqwebapp/js/main").eventize(self);
        self.nodeset.subscribe(function () {
            self.fire('change');
            self.showFilter(false);
        });
        self.nodesetCaseType.subscribe(function () {
            self.fire('change');
            self.nodeset("");
            self.showFilter(false);
            self.nodesetFilter("");
        });

        return self;
    };
});
