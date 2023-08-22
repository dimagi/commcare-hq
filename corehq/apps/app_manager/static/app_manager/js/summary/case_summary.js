hqDefine('app_manager/js/summary/case_summary',[
    'jquery',
    'underscore',
    'knockout',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/assert_properties',
    'app_manager/js/summary/models',
    'app_manager/js/menu',  // enable lang switcher and "Updates to publish" banner
    'hqwebapp/js/bootstrap3/knockout_bindings.ko', // popover
    'hqwebapp/js/bootstrap3/components.ko',    // search box
], function ($, _, ko, initialPageData, assertProperties, models) {

    var caseTypeModel = function (caseType) {
        var self = models.contentItemModel(caseType);

        self.properties = _.map(caseType.properties, function (property) {
            return models.contentItemModel(property);
        });

        // Convert these from objects to lists so knockout can process more easily
        self.relationshipList = _.map(_.keys(self.relationships), function (relationship) {
            return {
                relationship: relationship,
                caseType: self.relationships[relationship],
            };
        });
        self.openedByList = _.map(_.keys(self.opened_by), function (formId) {
            return {
                formId: formId,
                conditions: self.opened_by[formId].conditions,
            };
        });
        self.closedByList = _.map(_.keys(self.closed_by), function (formId) {
            return {
                formId: formId,
                conditions: self.closed_by[formId].conditions,
            };
        });

        return self;
    };

    var caseSummaryControlModel = function (viewModels) {
        var self = {};
        _.extend(self, models.controlModel({
            visibleAppIds: _.pluck(viewModels, 'appId'),
            versionUrlName: 'app_case_summary',
            query_label: gettext("Filter properties"),
            onQuery: function (query) {
                query = query.trim().toLowerCase();
                _.each(viewModels, function (viewModel) {
                    _.each(viewModel.caseTypes, function (caseType) {
                        var hasVisible = false;
                        _.each(caseType.properties, function (property) {
                            var isVisible = !query || property.name.indexOf(query) !== -1;
                            property.matchesQuery(isVisible);
                            if (!viewModel.showCalculations() && (query && isVisible && property.is_detail_calculation)) {
                                viewModel.showCalculations(true);
                            }
                            hasVisible = hasVisible || isVisible;
                        });
                        caseType.matchesQuery(hasVisible || !query && !caseType.properties.length);
                    });
                });
            },
            onSelectMenuItem: function (selectedId) {
                _.each(viewModels, function (viewModel) {
                    _.each(viewModel.caseTypes, function (caseType) {
                        caseType.isSelected(!selectedId || selectedId === caseType.name);
                    });
                });
            },
        }));

        self.showConditions = ko.observable(false);
        self.toggleConditions = function () {
            self.showConditions(!self.showConditions());
        };

        self.showCalculations = ko.observable(false);
        self.toggleCalculations = function () {
            self.showCalculations(!self.showCalculations());
        };

        return self;
    };

    var caseSummaryModel = function (options) {
        var self = models.contentModel(options);

        assertProperties.assertRequired(options, ['case_types']);
        self.caseTypes = _.map(options.case_types, function (caseType) {
            return caseTypeModel(caseType);
        });

        return self;
    };

    $(function () {
        var caseTypes = initialPageData.get("case_metadata").case_types;

        var caseSummaryMenu = models.menuModel({
            items: _.map(caseTypes, function (caseType) {
                return models.menuItemModel({
                    unique_id: caseType.name,
                    name: caseType.name,
                    icon: "fcc fcc-fd-external-case appnav-primary-icon",
                    has_errors: caseType.has_errors,
                    subitems: [],
                });
            }),
            viewAllItems: gettext("View All Cases"),
        });

        var caseSummaryContent = caseSummaryModel({
            case_types: caseTypes,
            form_name_map: initialPageData.get("form_name_map"),
            lang: initialPageData.get("lang"),
            langs: initialPageData.get("langs"),
            read_only: initialPageData.get("read_only"),
            appId: initialPageData.get("app_id"),
        });

        var caseSummaryController = caseSummaryControlModel([caseSummaryContent]);

        $("#case-summary-header").koApplyBindings(caseSummaryController);
        models.initVersionsBox(
            $("#version-selector"),
            {id: initialPageData.get("app_id"), text: initialPageData.get("app_version")}
        );
        models.initMenu([caseSummaryContent], caseSummaryMenu);
        models.initSummary(caseSummaryContent, caseSummaryController, "#case-summary");
    });
});
