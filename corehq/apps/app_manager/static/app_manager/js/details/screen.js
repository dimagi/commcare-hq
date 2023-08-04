/**
 * Model for case list/detail configuration. A screen contains the
 * entire configuration for either a case list or a case detail.
 * Both case list and case detail have a display properties table
 * for configuring DetailColumns. There's additional configuration
 * that may be specific to either case list or case detail, such as
 * sorting config (case list only), case search config (case list only),
 * nodeset column sorting (case detail only), etc.
 *
 * @param spec
 * @param config A detailScreenConfig object.
 * @param options
 */
hqDefine("app_manager/js/details/screen", function () {
    var Utils = hqImport('app_manager/js/details/utils'),
        ColumnModel = hqImport("app_manager/js/details/column");

    var getPropertyTitle = function (property) {
        // Strip "<prefix>:" before converting to title case.
        // This is aimed at prefixes like ledger: and attachment:
        property = property || '';
        var i = property.indexOf(":");
        return Utils.toTitleCase(property.substring(i + 1));
    };

    return function (spec, config, options) {
        var self = {};
        var i,
            columns;
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
        let detail = spec[self.columnKey];

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
        self.caseTileTemplateOptions = [[null, gettext("Don't Use Case Tiles")]].concat(options.caseTileTemplateOptions);
        self.caseTileTemplateOptions = self.caseTileTemplateOptions.map(function (templateOption) {
            return {templateValue: templateOption[0], templateName: templateOption[1]};
        });
        self.caseTileTemplate = ko.observable(detail.case_tile_template || null);
        self.caseTileTemplateConfigs = options.caseTileTemplateConfigs;
        self.caseTileFieldsForTemplate = ko.computed(function () {
            return (self.caseTileTemplateConfigs[self.caseTileTemplate()] || {}).fields;
        });
        self.caseTilePreviewForTemplate = ko.computed(function () {
            const grid = (self.caseTileTemplateConfigs[self.caseTileTemplate()] || {}).grid;
            if (!grid) {
                return "";
            }
            return "<div class='case-tile-preview'>" + _.map(grid, (values, fieldName) => {
                return _.template(`<div class='case-tile-preview-mapping'
                                        style='
                                            grid-area: <%= rowStart %> / <%= columnStart %> / <%= rowEnd %> / <%= columnEnd %>;
                                        '>
                                          <div style='
                                            justify-self: <%= horzAlign %>;
                                            text-align: <%= horzAlign %>;
                                            align-self: <%= vertAlign %>;
                                          '>
                                            <%= field %>
                                          </div>
                                        </div>`)({
                    rowStart: values.y + 1,
                    columnStart: values.x + 1,
                    rowEnd: values.y + values.height + 1,
                    columnEnd: values.x + values.width + 1,
                    horzAlign: values["horz-align"],
                    vertAlign: values["vert-align"],
                    field: fieldName,
                });
            }).join("") + "</div>";
        });
        self.showCaseTileColumn = ko.computed(function () {
            return self.caseTileTemplate() && hqImport('hqwebapp/js/toggles').toggleEnabled('CASE_LIST_TILE');
        });
        self.persistCaseContext = ko.observable(detail.persist_case_context || false);
        self.persistentCaseContextXML = ko.observable(detail.persistent_case_context_xml || 'case_name');

        self.caseTileGrouped = ko.observable(!!detail.case_tile_group.index_identifier || false);
        self.caseTileGroupBy = ko.observable(detail.case_tile_group.index_identifier);
        self.caseTileGroupHeaderRows = ko.observable(detail.case_tile_group.header_rows);

        self.customVariablesViewModel = {
            enabled: hqImport('hqwebapp/js/toggles').toggleEnabled('CASE_LIST_CUSTOM_VARIABLES'),
            xml: ko.observable(detail.custom_variables || ""),
        };
        self.customVariablesViewModel.xml.subscribe(function () {
            self.fireChange();
        });
        self.multiSelectEnabled = ko.observable(detail.multi_select);
        self.multiSelectEnabled.subscribe(function () {
            self.autoSelectEnabled(self.multiSelectEnabled() && self.autoSelectEnabled());
            self.fireChange();
        });
        self.maxSelectValue = ko.observable(detail.max_select_value);
        self.maxSelectValue.subscribe(function () {
            self.fireChange();
        });
        self.autoSelectEnabled = ko.observable(detail.auto_select);
        self.autoSelectEnabled.subscribe(function () {
            self.fireChange();
        });
        self.persistTileOnForms = ko.observable(detail.persist_tile_on_forms || false);
        self.enableTilePullDown = ko.observable(detail.pull_down_tile || false);
        self.allowsEmptyColumns = options.allowsEmptyColumns;
        self.persistentCaseTileFromModule = (
            ko.observable(detail.persistent_case_tile_from_module || ""));
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
                    const oldVal = column.header.val(),
                        newVal = getPropertyTitle(this.val());
                    column.header.val(newVal);
                    column.header.fire("change", {oldVal: oldVal, newVal: newVal});
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
                hqImport('app_manager/js/details/utils').setUpAutocomplete(column.field, self.properties);
            }
            column.header.on('change', function (e) {
                if (e.oldValue !== e.newValue) {
                    self.fire("columnChange", [{
                        "value": column,
                        "index": self.columns.indexOf(column),
                        "status": "edited"
                    }]);
                }
            })
            return column;
        };

        columns = detail.columns;
        // Inject tabs into the columns list:
        var tabs = detail.tabs || [];
        for (i = 0; i < tabs.length; i++) {
            columns.splice(
                tabs[i].starting_index + i,
                0,
                _.extend({
                    hasNodeset: tabs[i].has_nodeset,
                    nodeset: tabs[i].nodeset,
                    nodesetCaseType: tabs[i].nodeset_case_type,
                    nodesetFilter: tabs[i].nodeset_filter,
                }, _.pick(tabs[i], ["header", "isTab", "relevant"]))
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
        let saveButtonFire = () => self.saveButton.fire('change');
        self.on('change', saveButtonFire);
        self.caseTileTemplate.subscribe(saveButtonFire);
        self.persistCaseContext.subscribe(saveButtonFire);
        self.persistentCaseContextXML.subscribe(saveButtonFire);
        self.persistTileOnForms.subscribe(saveButtonFire);
        self.persistentCaseTileFromModule.subscribe(saveButtonFire);
        self.enableTilePullDown.subscribe(saveButtonFire);
        self.caseTileGrouped.subscribe(saveButtonFire);
        self.caseTileGroupBy.subscribe(saveButtonFire);
        self.caseTileGroupHeaderRows.subscribe(saveButtonFire);
        self.columns.subscribe(function (changes) {
            self.saveButton.fire('change');

            // create events when rows (column objects) are moved and fire a special event that allows us to update
            // dependent UI elements (sort properties)
            const events = changes
                // remove the 2nd event for column moves
                .filter(c => !(c.status === 'deleted' && c.moved !== undefined));

            // there should only be one 'change' now.
            const change = events[0];

            // for "moved" and "deleted" we need to add events for all the other columns that have changed their index
            let affectedColumns, move;  // 'move' is an index diff to calculate the previous index
            if (change.moved !== undefined) {
                const moveFrom = change.moved,
                    movedTo = change.index;
                if (movedTo > moveFrom) {
                    move = 1;
                    affectedColumns = self.columns.slice(moveFrom, movedTo);
                } else {
                    move = -1;
                    affectedColumns = self.columns.slice(movedTo + 1, moveFrom + 1);
                }
            } else if (change.status === 'deleted') {
                move = 1;
                affectedColumns = self.columns.slice(change.index);
            }
            if (affectedColumns) {
                affectedColumns.forEach(c => {
                    let index = self.columns.indexOf(c);
                    events.push({
                        value: c, index: index, status: "added", moved: index + move
                    })
                });
            }

            self.fire("columnChange", events);
        }, null, 'arrayChange');

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
            if (self.config.search.commonProperties().length > 0) {
                var msg = gettext("Search Properties and Default Search Filters can't have common properties. " +
                    "Please update following properties: ");
                errors.push(msg + self.config.search.commonProperties());
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
                        hqImport('app_manager/js/app_manager').updateDOM(data.update);
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

            data.caseTileTemplate = self.caseTileTemplate();
            data.persistCaseContext = self.persistCaseContext();
            data.persistentCaseContextXML = self.persistentCaseContextXML();
            data.persistTileOnForms = self.persistTileOnForms();
            data.persistentCaseTileFromModule = self.persistentCaseTileFromModule();
            data.enableTilePullDown = self.persistTileOnForms() ? self.enableTilePullDown() : false;
            
            data.case_tile_group = JSON.stringify({
                index_identifier: self.caseTileGrouped() ? self.caseTileGroupBy() : null,
                header_rows: self.caseTileGroupHeaderRows()
            });

            if (self.containsParentConfiguration) {
                var parentSelect;
                if (_.has(self.config, 'parentSelect')) {
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
                if (_.has(self.config, 'fixtureSelect')) {
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
            data.multi_select = self.multiSelectEnabled();
            data.auto_select = self.autoSelectEnabled();
            data.max_select_value = self.maxSelectValue();
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
});
