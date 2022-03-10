/**
 * Model for Lookup Table Case Selection in case list configuration.
 */
hqDefine("app_manager/js/details/fixture_select", function () {
    return function (init) {
        var self = {};
        self.active = ko.observable(init.active);
        self.fixtureType = ko.observable(init.fixtureType);
        self.displayColumn = ko.observable(init.displayColumn);
        self.localize = ko.observable(init.localize);
        self.variableColumn = ko.observable(init.variableColumn);
        self.xpath = ko.observable(init.xpath);
        self.fixture_columns = ko.computed(function () {
            var columns = init.fixture_columns_by_type[self.fixtureType()],
                defaultOption = [gettext("Select One")];
            return defaultOption.concat(columns);
        });
        return self;
    };
});