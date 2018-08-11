hqDefine('app_manager/js/summary/case_summary', function() {
    var assertProperties = hqImport("hqwebapp/js/assert_properties").assert,
        initialPageData = hqImport("hqwebapp/js/initial_page_data"),
        menu = hqImport("app_manager/js/summary/menu"),
        utils = hqImport("app_manager/js/summary/utils");

    var propertyModel = function(property) {
        var self = _.extend({}, property);

        _.each(self.forms, function(form) {
            _.each(form.load_questions, function(questionAndConditions) {
                questionAndConditions.question = utils.questionModel(questionAndConditions.question);
            });
            _.each(form.save_questions, function(questionAndConditions) {
                questionAndConditions.question = utils.questionModel(questionAndConditions.question);
            });
        });

        self.isVisible = ko.observable(true);
        return self;
    };

    var caseTypeModel = function(caseType) {
        var self = _.extend({}, caseType);

        self.properties = _.map(caseType.properties, function(property) {
            return propertyModel(property);
        });

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
        self.hasVisibleProperties = ko.observable(true);
        self.isVisible = ko.computed(function() {
            return self.isSelected() && self.hasVisibleProperties();
        });

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

        self.query = ko.observable('');
        self.clearQuery = function() {
            self.query('');
        };
        self.query.subscribe(_.debounce(function(newValue) {
            _.each(self.caseTypes, function(caseType) {
                var hasVisible = false;
                _.each(caseType.properties, function(property) {
                    var isVisible = !newValue || property.name.indexOf(newValue) !== -1;
                    property.isVisible(isVisible);
                    hasVisible = hasVisible || isVisible;
                });
                caseType.hasVisibleProperties(hasVisible || !newValue && !caseType.properties.length);
            });
        }, 200));

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
