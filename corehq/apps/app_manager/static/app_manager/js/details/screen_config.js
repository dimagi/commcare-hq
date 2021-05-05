/**
 * Model for the entire case list + case detail configuration UI.
 */
hqDefine('app_manager/js/details/screen_config', function () {
    return function (spec) {
        var self = {};
        self.properties = spec.properties;
        self.screens = [];
        self.model = spec.model || 'case';
        self.lang = spec.lang;
        self.langs = spec.langs || [];
        self.multimedia = spec.multimedia || {};
        self.module_id = spec.module_id || '';
        if (_.has(spec, 'parentSelect') && spec.parentSelect) {
            self.parentSelect = hqImport("app_manager/js/details/parent_select")({
                active: spec.parentSelect.active,
                moduleId: spec.parentSelect.module_id,
                relationship: spec.parentSelect.relationship,
                parentModules: spec.parentModules,
                allCaseModules: spec.allCaseModules,
                lang: self.lang,
                langs: self.langs,
            });
        }

        if (_.has(spec, 'fixtureSelect') && spec.fixtureSelect) {
            self.fixtureSelect = hqImport("app_manager/js/details/fixture_select")({
                active: spec.fixtureSelect.active,
                fixtureType: spec.fixtureSelect.fixture_type,
                displayColumn: spec.fixtureSelect.display_column,
                localize: spec.fixtureSelect.localize,
                variableColumn: spec.fixtureSelect.variable_column,
                xpath: spec.fixtureSelect.xpath,
                fixture_columns_by_type: spec.fixture_columns_by_type,
            });
        }
        self.saveUrl = spec.saveUrl;

        /**
         * Add a screenModel to self detailScreenConfig
         * @param pair
         * @param columnType
         * The type of case properties self self screenModel will be displaying,
         * either "short" or "long".
         */
        function addScreen(pair, columnType) {

            var screen = hqImport("app_manager/js/details/screen")(
                pair,
                self, {
                    lang: self.lang,
                    langs: self.langs,
                    properties: self.properties,
                    saveUrl: self.saveUrl,
                    columnKey: columnType,
                    childCaseTypes: spec.childCaseTypes,
                    fixtures: _.keys(spec.fixture_columns_by_type),
                    containsSortConfiguration: columnType === "short",
                    containsParentConfiguration: columnType === "short",
                    containsFixtureConfiguration: (columnType === "short" && hqImport('hqwebapp/js/toggles').toggleEnabled('FIXTURE_CASE_SELECTION')),
                    containsFilterConfiguration: columnType === "short",
                    containsCaseListLookupConfiguration: (columnType === "short" && (hqImport('hqwebapp/js/toggles').toggleEnabled('CASE_LIST_LOOKUP') || hqImport('hqwebapp/js/toggles').toggleEnabled('BIOMETRIC_INTEGRATION'))),
                    // TODO: Check case_search_enabled_for_domain(), not toggle. FB 225343
                    containsSearchConfiguration: (columnType === "short" && hqImport('hqwebapp/js/toggles').toggleEnabled('SYNC_SEARCH_CASE_CLAIM')),
                    containsCustomXMLConfiguration: columnType === "short",
                    allowsTabs: columnType === 'long',
                    allowsEmptyColumns: columnType === 'long',
                }
            );
            self.screens.push(screen);
            return screen;
        }

        if (spec.state.short !== undefined) {
            self.shortScreen = addScreen(spec.state, "short");
            // Set up filter
            var filterXpath = spec.state.short.filter;
            self.filter = hqImport("app_manager/js/details/filter")(filterXpath ? filterXpath : null, self.shortScreen.saveButton);
            // Set up sortRows
            self.sortRows = hqImport("app_manager/js/details/sort_rows")(self.properties, self.shortScreen.saveButton);
            if (spec.sortRows) {
                for (var j = 0; j < spec.sortRows.length; j++) {
                    self.sortRows.addSortRow(
                        spec.sortRows[j].field,
                        spec.sortRows[j].type,
                        spec.sortRows[j].direction,
                        spec.sortRows[j].blanks,
                        spec.sortRows[j].display[self.lang],
                        false,
                        spec.sortRows[j].sort_calculation
                    );
                }
            }
            self.customXMLViewModel = {
                enabled: hqImport('hqwebapp/js/toggles').toggleEnabled('CASE_LIST_CUSTOM_XML'),
                xml: ko.observable(spec.state.short.custom_xml || ""),
            };
            self.customXMLViewModel.xml.subscribe(function () {
                self.shortScreen.saveButton.fire("change");
            });
            var $caseListLookup = $("#" + spec.state.type + "-list-callout-configuration");
            self.caseListLookup = hqImport("app_manager/js/details/case_list_callout").caseListLookupViewModel(
                $caseListLookup,
                spec.state.short,
                spec.lang,
                self.shortScreen.saveButton
            );
            // Set up case search
            var caseClaimModels = hqImport("app_manager/js/details/case_claim");
            self.search = caseClaimModels.searchViewModel(
                spec.searchProperties || [],
                spec.defaultProperties,
                _.pick(spec, caseClaimModels.searchConfigKeys),
                spec.lang,
                self.shortScreen.saveButton,
                self.filter.filterText
            );
        }
        if (spec.state.long !== undefined) {
            var printModule = hqImport("app_manager/js/details/case_detail_print"),
                printRef = printModule.getPrintRef(),
                printTemplateUploader = printModule.getPrintTemplateUploader();
            self.longScreen = addScreen(spec.state, "long");
            self.printTemplateReference = _.extend(printRef, {
                removePrintTemplate: function () {
                    $.post(
                        hqImport("hqwebapp/js/initial_page_data").reverse("hqmedia_remove_detail_print_template"), {
                            module_unique_id: spec.moduleUniqueId,
                        },
                        function (data, status) {
                            if (status === 'success') {
                                printRef.setObjReference({
                                    path: printRef.path,
                                });
                                printRef.is_matched(false);
                                printTemplateUploader.updateUploadFormUI();
                            }
                        }
                    );
                },
            });
        }
        return self;
    };
});

ko.bindingHandlers.DetailScreenConfig_notifyShortScreenOnChange = {
    init: function (element, valueAccessor) {
        var $root = valueAccessor();
        setTimeout(function () {
            $(element).on('change', '*', function () {
                $root.shortScreen.fire('change');
            });
        }, 0);
    },
};

ko.bindingHandlers.addSaveButtonListener = {
    init: function (element, valueAccessor, allBindings, viewModel, bindingContext) {
        bindingContext.$parent.initSaveButtonListeners($(element).parent());
    },
};
