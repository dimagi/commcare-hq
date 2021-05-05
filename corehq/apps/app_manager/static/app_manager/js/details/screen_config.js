/*globals $, _, DOMPurify, hqDefine, hqImport */

hqDefine('app_manager/js/details/screen_config', function () {
    var module = {};

    var filterViewModel = function (filterText, saveButton) {
        var self = {};
        self.filterText = ko.observable(typeof filterText === "string" && filterText.length > 0 ? filterText : "");
        self.showing = ko.observable(self.filterText() !== "");

        self.filterText.subscribe(function () {
            saveButton.fire('change');
        });
        self.showing.subscribe(function () {
            saveButton.fire('change');
        });

        self.serialize = function () {
            if (self.showing()) {
                return self.filterText();
            }
            return null;
        };
        return self;
    };

    module.parentSelect = function (init) {
        var self = {};
        var defaultModule = _(init.parentModules).findWhere({
            is_parent: true,
        });
        self.moduleId = ko.observable(init.moduleId || (defaultModule ? defaultModule.unique_id : null));
        self.allCaseModules = ko.observable(init.allCaseModules);
        self.parentModules = ko.observable(init.parentModules);
        self.lang = ko.observable(init.lang);
        self.langs = ko.observable(init.langs);
        self.enableOtherOption = hqImport('hqwebapp/js/toggles').toggleEnabled('NON_PARENT_MENU_SELECTION');

        self.selectOptions = [
            {id: 'none', text: gettext('None')},
            {id: 'parent', text: gettext('Parent')},
        ];
        if (self.enableOtherOption) {
            self.selectOptions.push(
                {id: 'other', text: gettext('Other')}
            );
        }
        var selectMode = init.active ? (init.relationship === 'parent' ? 'parent' : 'other') : 'none';
        if (self.enableOtherOption) {
            self.selectMode = ko.observable(selectMode);
            self.active = ko.computed(function () {
                return (self.selectMode() !== 'none');
            });
        }
        else {
            self.active = ko.observable(init.active);
            self.selectMode = ko.computed(function () {
                return self.active ? 'parent' : 'none';
            });
        }
        self.relationship = ko.computed(function () {
            return (self.selectMode() === 'parent' || self.selectMode() === 'none') ? 'parent' : null ;
        });

        function getTranslation(name, langs) {
            var firstLang = _(langs).find(function (lang) {
                return name[lang];
            });
            return name[firstLang];
        }
        self.dropdownModules = ko.computed(function () {
            return (self.selectMode() === 'parent') ? self.parentModules() : self.allCaseModules();
        });
        self.hasError = ko.computed(function () {
            return !_.contains(_.pluck(self.dropdownModules(), 'unique_id'), self.moduleId());
        });
        self.moduleOptions = ko.computed(function () {
            var options = _(self.dropdownModules()).map(function (module) {
                var STAR = '\u2605',
                    SPACE = '\u3000';
                var marker = (module.is_parent ? STAR : SPACE);
                return {
                    value: module.unique_id,
                    label: marker + ' ' + getTranslation(module.name, [self.lang()].concat(self.langs())),
                };
            });
            if (self.hasError()) {
                options.unshift({
                    value: '',
                    label: gettext('Unknown menu'),
                });
            }
            return options;
        });
        return self;
    };

    var fixtureSelect = function (init) {
        var self = {};
        self.active = ko.observable(init.active);
        self.fixtureType = ko.observable(init.fixtureType);
        self.displayColumn = ko.observable(init.displayColumn);
        self.localize = ko.observable(init.localize);
        self.variableColumn = ko.observable(init.variableColumn);
        self.xpath = ko.observable(init.xpath);
        self.fixture_columns = ko.computed(function () {
            var columns_for_type = init.fixture_columns_by_type[self.fixtureType()],
                default_option = [gettext("Select One")];
            return default_option.concat(columns_for_type);
        });
        return self;
    };

    module.detailScreenConfig = (function () {
        "use strict";

        var detailScreenConfig = (function () {
            var detailScreenConfigFunc = function (spec) {
                var self = {};
                self.properties = spec.properties;
                self.screens = [];
                self.model = spec.model || 'case';
                self.lang = spec.lang;
                self.langs = spec.langs || [];
                self.multimedia = spec.multimedia || {};
                self.module_id = spec.module_id || '';
                if (spec.hasOwnProperty('parentSelect') && spec.parentSelect) {
                    self.parentSelect = module.parentSelect({
                        active: spec.parentSelect.active,
                        moduleId: spec.parentSelect.module_id,
                        relationship: spec.parentSelect.relationship,
                        parentModules: spec.parentModules,
                        allCaseModules: spec.allCaseModules,
                        lang: self.lang,
                        langs: self.langs,
                    });
                }

                if (spec.hasOwnProperty('fixtureSelect') && spec.fixtureSelect) {
                    self.fixtureSelect = fixtureSelect({
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
                    var filter_xpath = spec.state.short.filter;
                    self.filter = filterViewModel(filter_xpath ? filter_xpath : null, self.shortScreen.saveButton);
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
                    self.customXMLViewModel.xml.subscribe(function (v) {
                        self.shortScreen.saveButton.fire("change");
                    });
                    var $case_list_lookup_el = $("#" + spec.state.type + "-list-callout-configuration");
                    self.caseListLookup = hqImport("app_manager/js/details/case_list_callout").caseListLookupViewModel(
                        $case_list_lookup_el,
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
            detailScreenConfigFunc.init = function (spec) {
                return detailScreenConfigFunc(spec);
            };
            return detailScreenConfigFunc;
        }());

        return detailScreenConfig;
    }());

    return module;

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
