/*globals $, _, DOMPurify, hqDefine, hqImport */

hqDefine('app_manager/js/details/screen_config', function () {
    var module = {},
        uiElement = hqImport('hqwebapp/js/ui-element');


    // saveButton is a required parameter
    var sortRow = function (params) {
        var PropertyUtils = hqImport('app_manager/js/details/display_property_utils'),
            self = {};
        params = params || {};

        self.selectField = uiElement.select(params.properties).val(typeof params.field !== 'undefined' ? params.field : "");
        PropertyUtils.setUpAutocomplete(self.selectField, params.properties);
        self.sortCalculation = ko.observable(typeof params.sortCalculation !== 'undefined' ? params.sortCalculation : "");

        self.showWarning = ko.observable(false);
        self.hasValidPropertyName = function () {
            return PropertyUtils.isValidPropertyName(self.selectField.val());
        };
        self.display = ko.observable(typeof params.display !== 'undefined' ? params.display : "");
        self.display.subscribe(function () {
            self.notifyButton();
        });
        self.toTitleCase = PropertyUtils.toTitleCase;
        self.selectField.on('change', function () {
            if (!self.hasValidPropertyName()) {
                self.showWarning(true);
            } else {
                self.showWarning(false);
                self.display(self.toTitleCase(this.val()));
                self.notifyButton();
            }
        });

        self.type = ko.observable(typeof params.type !== 'undefined' ? params.type : "");
        self.type.subscribe(function () {
            self.notifyButton();
        });
        self.direction = ko.observable(params.direction || "ascending");
        self.blanks = ko.observable(params.blanks || (params.direction === "descending" ? "last" : "first"));
        self.direction.subscribe(function () {
            self.notifyButton();
        });
        self.blanks.subscribe(function () {
            self.notifyButton();
        });
        self.sortCalculation.subscribe(function () {
            self.notifyButton();
        });

        self.notifyButton = function () {
            params.saveButton.fire('change');
        };

        self.ascendText = ko.computed(function () {
            var type = self.type();
            // This is here for the CACHE_AND_INDEX feature
            if (type === 'plain' || type === 'index') {
                return gettext('Increasing (a, b, c)');
            } else if (type === 'date') {
                return gettext('Increasing (May 1st, May 2nd)');
            } else if (type === 'int') {
                return gettext('Increasing (1, 2, 3)');
            } else if (type === 'double' || type === 'distance') {
                return gettext('Increasing (1.1, 1.2, 1.3)');
            }
        });

        self.descendText = ko.computed(function () {
            var type = self.type();
            if (type === 'plain' || type === 'index') {
                return gettext('Decreasing (c, b, a)');
            } else if (type === 'date') {
                return gettext('Decreasing (May 2nd, May 1st)');
            } else if (type === 'int') {
                return gettext('Decreasing (3, 2, 1)');
            } else if (type === 'double' || type === 'distance') {
                return gettext('Decreasing (1.3, 1.2, 1.1)');
            }
        });

        return self;
    };

    /**
     *
     * @param properties
     * @param saveButton
     * The button that should be activated when something changes
     * @constructor
     */
    var sortRows = function (properties, saveButton) {
        var self = {};
        self.sortRows = ko.observableArray([]);

        self.addSortRow = function (field, type, direction, blanks, display, notify, sortCalculation) {
            self.sortRows.push(sortRow({
                field: field,
                type: type,
                direction: direction,
                blanks: blanks,
                display: display,
                saveButton: saveButton,
                properties: properties,
                sortCalculation: sortCalculation,
            }));
            if (notify) {
                saveButton.fire('change');
            }
        };
        self.removeSortRow = function (row) {
            self.sortRows.remove(row);
            saveButton.fire('change');
        };

        self.rowCount = ko.computed(function () {
            return self.sortRows().length;
        });

        self.showing = ko.computed(function () {
            return self.rowCount() > 0;
        });

        return self;
    };

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
        var PropertyUtils = hqImport('app_manager/js/details/display_property_utils'),
            ColumnModel = hqImport("app_manager/js/details/column");

        function getPropertyTitle(property) {
            // Strip "<prefix>:" before converting to title case.
            // This is aimed at prefixes like ledger: and attachment:
            property = property || '';
            var i = property.indexOf(":");
            return PropertyUtils.toTitleCase(property.substring(i + 1));
        }

        var detailScreenConfig, screenModel;

        screenModel = (function () {
            /**
             * The screenModel "Class" is in charge of inserting a table into the DOM that
             * contains rows for each case DetailColumn. It also handles the
             * reordering of these columns through drag and drop as well as
             * saving them on the server.
             * @param $home jQuery object where the screenModel will be rendered
             * @param spec
             * @param config A detailScreenConfig object.
             * @param options
             * @constructor
             */
            var screenModelFunc = function(spec, config, options) {
                var self = {};
                var i, column, model, property, header, columns;
                hqImport("hqwebapp/js/main").eventize(self);
                self.type = spec.type;
                self.saveUrl = options.saveUrl;
                self.config = config;
                self.columns = ko.observableArray([]);
                self.model = config.model;
                self.lang = options.lang;
                self.langs = options.langs || [];
                self.properties = options.properties;
                self.childCaseTypes = options.childCaseTypes;
                self.fixtures = options.fixtures;
                // The column key is used to retrieve the columns from the spec and
                // as the name of the key in the data object that is sent to the
                // server on save.
                self.columnKey = options.columnKey;
                // Not all screenModel instances will handle sorting, parent selection,
                // and filtering. E.g The "Case Detail" tab only handles the module's
                // "long" case details. These flags will make sure this instance
                // doesn't try to save these configurations if it is not in charge
                // of these configurations.
                self.containsSortConfiguration = options.containsSortConfiguration;
                self.containsParentConfiguration = options.containsParentConfiguration;
                self.containsFixtureConfiguration = options.containsFixtureConfiguration;
                self.containsFilterConfiguration = options.containsFilterConfiguration;
                self.containsCaseListLookupConfiguration = options.containsCaseListLookupConfiguration;
                self.containsSearchConfiguration = options.containsSearchConfiguration;
                self.containsCustomXMLConfiguration = options.containsCustomXMLConfiguration;
                self.allowsTabs = options.allowsTabs;
                self.useCaseTiles = ko.observable(spec[self.columnKey].use_case_tiles ? "yes" : "no");
                self.showCaseTileColumn = ko.computed(function () {
                    return self.useCaseTiles() === "yes" && hqImport('hqwebapp/js/toggles').toggleEnabled('CASE_LIST_TILE');
                });
                self.persistCaseContext = ko.observable(spec[self.columnKey].persist_case_context || false);
                self.persistentCaseContextXML = ko.observable(spec[self.columnKey].persistent_case_context_xml || 'case_name');
                self.customVariablesViewModel = {
                    enabled: hqImport('hqwebapp/js/toggles').toggleEnabled('CASE_LIST_CUSTOM_VARIABLES'),
                    xml: ko.observable(spec[self.columnKey].custom_variables || ""),
                };
                self.customVariablesViewModel.xml.subscribe(function () {
                    self.fireChange();
                });
                self.persistTileOnForms = ko.observable(spec[self.columnKey].persist_tile_on_forms || false);
                self.enableTilePullDown = ko.observable(spec[self.columnKey].pull_down_tile || false);
                self.allowsEmptyColumns = options.allowsEmptyColumns;
                self.persistentCaseTileFromModule = (
                    ko.observable(spec[self.columnKey].persistent_case_tile_from_module || ""));
                self.sortNodesetColumns = ko.observable(spec[self.columnKey].sort_nodeset_columns || false);
                self.fireChange = function () {
                    self.fire('change');
                };

                self.initColumnAsColumn = function (column) {
                    column.model.setEdit(false);
                    column.field.setEdit(true);
                    column.header.setEdit(true);
                    column.format.setEdit(true);
                    column.date_extra.setEdit(true);
                    column.enum_extra.setEdit(true);
                    column.late_flag_extra.setEdit(true);
                    column.filter_xpath_extra.setEdit(true);
                    column.calc_xpath_extra.setEdit(true);
                    column.time_ago_extra.setEdit(true);
                    column.setGrip(true);
                    column.on('change', self.fireChange);

                    column.field.on('change', function () {
                        if (!column.useXpathExpression) {
                            column.header.val(getPropertyTitle(this.val()));
                            column.header.fire("change");
                        }
                    });
                    if (column.original.hasAutocomplete) {
                        var options = self.properties;
                        if (column.original.field && !_.contains(column.original.field)) {
                            options = [column.original.field].concat(options);
                        }
                        column.field.setOptions(options);
                        column.field.val(column.original.field);
                        column.field.observableVal(column.original.field);
                        hqImport('app_manager/js/details/display_property_utils').setUpAutocomplete(column.field, self.properties);
                    }
                    return column;
                };

                columns = spec[self.columnKey].columns;
                // Inject tabs into the columns list:
                var tabs = spec[self.columnKey].tabs || [];
                for (i = 0; i < tabs.length; i++) {
                    columns.splice(
                        tabs[i].starting_index + i,
                        0,
                        _.extend({
                            hasNodeset: tabs[i].has_nodeset,
                        }, _.pick(tabs[i], ["header", "nodeset", "isTab", "relevant"]))
                    );
                }
                if (self.columnKey === 'long') {
                    self.addTab = function (hasNodeset) {
                        var col = self.initColumnAsColumn(ColumnModel({
                            isTab: true,
                            hasNodeset: hasNodeset,
                            model: 'tab',
                        }, self));
                        self.columns.splice(0, 0, col);
                    };
                }

                // Filters are a type of DetailColumn on the server. Don't display
                // them with the other columns though
                columns = _.filter(columns, function (col) {
                    return col.format !== "filter";
                });

                // set up the columns
                for (i = 0; i < columns.length; i += 1) {
                    self.columns.push(ColumnModel(columns[i], self));
                    self.initColumnAsColumn(self.columns()[i]);
                }

                self.saveButton = hqImport("hqwebapp/js/main").initSaveButton({
                    unsavedMessage: gettext('You have unsaved detail screen configurations.'),
                    save: function () {
                        self.save();
                    },
                });
                self.on('change', function () {
                    self.saveButton.fire('change');
                });
                self.useCaseTiles.subscribe(function () {
                    self.saveButton.fire('change');
                });
                self.persistCaseContext.subscribe(function () {
                    self.saveButton.fire('change');
                });
                self.persistentCaseContextXML.subscribe(function () {
                    self.saveButton.fire('change');
                });
                self.persistTileOnForms.subscribe(function () {
                    self.saveButton.fire('change');
                });
                self.persistentCaseTileFromModule.subscribe(function () {
                    self.saveButton.fire('change');
                });
                self.enableTilePullDown.subscribe(function () {
                    self.saveButton.fire('change');
                });
                self.sortNodesetColumns.subscribe(function () {
                    self.saveButton.fire('change');
                });
                self.columns.subscribe(function () {
                    self.saveButton.fire('change');
                });

                self.save = function () {
                    // Only save if property names are valid
                    var errors = [],
                        containsTab = false;
                    _.each(self.columns(), function (column) {
                        column.saveAttempted(true);
                        if (column.isTab) {
                            containsTab = true;
                            if (column.showWarning()) {
                                errors.push(gettext("There is an error in your tab: ") + column.field.value);
                            }
                        } else if (column.showWarning()) {
                            errors.push(gettext("There is an error in your property name: ") + column.field.value);
                        }
                    });
                    if (containsTab) {
                        if (!self.columns()[0].isTab) {
                            errors.push(gettext("All properties must be below a tab."));
                        }
                    }
                    if (errors.length) {
                        alert(gettext("There are errors in your configuration.") + "\n" + errors.join("\n"));
                        return;
                    }

                    if (self.containsSortConfiguration) {
                        var sortRows = self.config.sortRows.sortRows();
                        for (var i = 0; i < sortRows.length; i++) {
                            var row = sortRows[i];
                            if (!row.hasValidPropertyName()) {
                                row.showWarning(true);
                            }
                        }
                    }
                    if (self.validate()) {
                        self.saveButton.ajax({
                            url: self.saveUrl,
                            type: "POST",
                            data: self.serialize(),
                            dataType: 'json',
                            success: function (data) {
                                var app_manager = hqImport('app_manager/js/app_manager');
                                app_manager.updateDOM(data.update);
                            },
                        });
                    }
                };
                self.validate = function () {
                    if (self.containsCaseListLookupConfiguration) {
                        return self.config.caseListLookup.validate();
                    }
                    return true;
                };
                self.serialize = function () {
                    var columns = self.columns();
                    var data = {
                        type: JSON.stringify(self.type),
                    };

                    // Add columns
                    data[self.columnKey] = JSON.stringify(_.map(
                        _.filter(columns, function (c) {
                            return !c.isTab;
                        }),
                        function (c) {
                            return c.serialize();
                        }
                    ));

                    // Add tabs
                    // calculate the starting index for each Tab
                    var acc = 0;
                    for (var j = 0; j < columns.length; j++) {
                        var c = columns[j];
                        if (c.isTab) {
                            c.starting_index = acc;
                        } else {
                            acc++;
                        }
                    }
                    data.tabs = JSON.stringify(_.map(
                        _.filter(columns, function (c) {
                            return c.isTab;
                        }),
                        function (c) {
                            return c.serialize();
                        }
                    ));

                    data.useCaseTiles = self.useCaseTiles() === "yes";
                    data.persistCaseContext = self.persistCaseContext();
                    data.persistentCaseContextXML = self.persistentCaseContextXML();
                    data.persistTileOnForms = self.persistTileOnForms();
                    data.persistentCaseTileFromModule = self.persistentCaseTileFromModule();
                    data.enableTilePullDown = self.persistTileOnForms() ? self.enableTilePullDown() : false;
                    data.sortNodesetColumns = self.sortNodesetColumns() ? self.sortNodesetColumns() : false;

                    if (self.containsParentConfiguration) {
                        var parentSelect;
                        if (self.config.hasOwnProperty('parentSelect')) {
                            parentSelect = {
                                module_id: self.config.parentSelect.moduleId(),
                                relationship: self.config.parentSelect.relationship(),
                                active: self.config.parentSelect.active(),
                            };
                        }
                        data.parent_select = JSON.stringify(parentSelect);
                    }
                    if (self.containsFixtureConfiguration) {
                        var fixtureSelect;
                        if (self.config.hasOwnProperty('fixtureSelect')) {
                            fixtureSelect = {
                                active: self.config.fixtureSelect.active(),
                                fixture_type: self.config.fixtureSelect.fixtureType(),
                                display_column: self.config.fixtureSelect.displayColumn(),
                                localize: self.config.fixtureSelect.localize(),
                                variable_column: self.config.fixtureSelect.variableColumn(),
                                xpath: self.config.fixtureSelect.xpath(),
                            };
                        }
                        data.fixture_select = JSON.stringify(fixtureSelect);
                    }
                    if (self.containsSortConfiguration) {
                        data.sort_elements = JSON.stringify(_.map(self.config.sortRows.sortRows(), function (row) {
                            return {
                                field: row.selectField.val(),
                                type: row.type(),
                                direction: row.direction(),
                                blanks: row.blanks(),
                                display: row.display(),
                                sort_calculation: row.sortCalculation(),
                            };
                        }));
                    }
                    if (self.containsFilterConfiguration) {
                        data.filter = JSON.stringify(self.config.filter.serialize());
                    }
                    if (self.containsCaseListLookupConfiguration) {
                        data.case_list_lookup = JSON.stringify(self.config.caseListLookup.serialize());
                    }
                    if (self.containsCustomXMLConfiguration) {
                        data.custom_xml = self.config.customXMLViewModel.xml();
                    }
                    data[self.columnKey + '_custom_variables'] = self.customVariablesViewModel.xml();
                    if (self.containsSearchConfiguration) {
                        data.search_properties = JSON.stringify(self.config.search.serialize());
                    }
                    return data;
                };
                self.addItem = function (columnConfiguration, index) {
                    var column = self.initColumnAsColumn(
                        ColumnModel(columnConfiguration, self)
                    );
                    if (index === undefined) {
                        self.columns.push(column);
                    } else {
                        self.columns.splice(index, 0, column);
                    }
                    column.useXpathExpression = !!columnConfiguration.useXpathExpression;
                };
                self.pasteCallback = function (data, index) {
                    try {
                        data = JSON.parse(data);
                    } catch (e) {
                        // just ignore pasting non-json
                        return;
                    }
                    if (data.type === 'detail-screen-config:Column' && data.contents) {
                        self.addItem(data.contents, index);
                    }
                };
                self.addProperty = function () {
                    var type = self.columnKey === "short" ? "List" : "Detail";
                    hqImport('analytix/js/google').track.event('Case Management', 'Module Level Case ' + type, 'Add Property');
                    self.addItem({
                        hasAutocomplete: true,
                    });
                };
                self.addGraph = function () {
                    self.addItem({
                        hasAutocomplete: false,
                        format: 'graph',
                    });
                };
                self.addXpathExpression = function () {
                    self.addItem({
                        hasAutocomplete: false,
                        useXpathExpression: true,
                    });
                };

                return self;
            };

            screenModelFunc.init = function (spec, config, options) {
                return screenModelFunc(spec, config, options);
            };
            return screenModelFunc;
        }());
        detailScreenConfig = (function () {
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
                self.contextVariables = spec.contextVariables;

                /**
                 * Add a screenModel to self detailScreenConfig
                 * @param pair
                 * @param columnType
                 * The type of case properties self self screenModel will be displaying,
                 * either "short" or "long".
                 */
                function addScreen(pair, columnType) {

                    var screen = screenModel.init(
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
                    self.sortRows = sortRows(self.properties, self.shortScreen.saveButton);
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

    /* for sharing variables between essentially separate parts of the ui */
    module.state = {
        requires_case_details: ko.observable(),
    };
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
