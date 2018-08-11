hqDefine('app_manager/js/summary/case_summary', function() {
    var assertProperties = hqImport("hqwebapp/js/assert_properties").assert,
        initialPageData = hqImport("hqwebapp/js/initial_page_data"),
        menu = hqImport("app_manager/js/summary/menu");

    var caseTypeModel = function(caseType) {
        var self = _.extend({}, caseType);

        // Convert these from objects to lists so knockout can process more easily
        self.relationshipList = _.map(_.keys(self.relationships), function(relationship) {
            return {
                relationship: relationship,
                caseType: self.relationships[relationship],
            };
        });
        self.openedByList = _.map(_.keys(self.opened_by), function(formId) {
            return {
                formId: formId,
                conditions: self.opened_by[formId].conditions,
            };
        });
        self.closedByList = _.map(_.keys(self.closed_by), function(formId) {
            return {
                formId: formId,
                conditions: self.closed_by[formId].conditions,
            };
        });

        self.isSelected = ko.observable(true);

        return self;
    };

    var contentModel = function(options) {
        assertProperties(options, ['case_types'], []);

        var self = {};
        self.caseTypes = _.map(options.case_types, function(caseType) {
            return caseTypeModel(caseType);
        });

        self.selectedItemId = ko.observable('');      // blank indicates "View All"
        self.selectedItemId.subscribe(function(selectedId) {
            _.each(self.caseTypes, function(caseType) {
                caseType.isSelected(!selectedId || selectedId === caseType.name);
            });
        });

        self.showConditions = ko.observable(true);
        self.toggleConditions = function() {
            self.showConditions(!self.showConditions());
        };

        return self;
    };

    $(function() {
        var caseTypes = initialPageData.get("case_metadata").case_types;

        var caseSummaryMenu = menu.menuModel({
            items: _.map(caseTypes, function(caseType) {
                return menu.menuItemModel({
                    id: caseType.name,
                    name: caseType.name,
                    icon: "fcc fcc-fd-external-case appnav-primary-icon",
                    subitems: [],
                });
            }),
            viewAllItems: gettext("View All Cases"),
        });

        var caseSummaryContent = contentModel({
            case_types: caseTypes,
        });

        hqImport("hqwebapp/js/layout").setIsAppbuilderResizing(true);
        $("#hq-sidebar > nav").koApplyBindings(caseSummaryMenu);
        $("#js-appmanager-body").koApplyBindings(caseSummaryContent);

        caseSummaryMenu.selectedItemId.subscribe(function(newValue) {
            caseSummaryContent.selectedItemId(newValue);
        });
    });
});
