hqDefine('app_manager/js/summary/case_summary', function() {
    var assertProperties = hqImport("hqwebapp/js/assert_properties").assert,
        initialPageData = hqImport("hqwebapp/js/initial_page_data"),
        menu = hqImport("app_manager/js/summary/menu");

    var caseTypeModel = function(caseType) {
        var self = _.extend({}, caseType);

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

        $("#hq-sidebar > nav").koApplyBindings(caseSummaryMenu);
        $("#js-appmanager-body").koApplyBindings(caseSummaryContent);

        caseSummaryMenu.selectedItemId.subscribe(function(newValue) {
            caseSummaryContent.selectedItemId(newValue);
        });
    });
});
