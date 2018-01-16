/*globals $, _, DOMPurify, hqDefine, hqImport */

hqDefine('app_manager/js/details/screen_config', function () {
    var module = {},
        uiElement = hqImport('hqwebapp/js/ui-element');

    module.CC_DETAIL_SCREEN = {
        getFieldHtml: function (field) {
            var text = field;
            if (module.CC_DETAIL_SCREEN.isAttachmentProperty(text)) {
                text = text.substring(text.indexOf(":") + 1);
            }
            var parts = text.split('/');
            // wrap all parts but the last in a label style
            for (var j = 0; j < parts.length - 1; j++) {
                parts[j] = ('<span class="label label-info">'
                            + parts[j] + '</span>');
            }
            if (parts[j][0] == '#') {
                parts[j] = ('<span class="label label-info">'
                            + module.CC_DETAIL_SCREEN.toTitleCase(parts[j]) + '</span>');
            } else {
                parts[j] = ('<code style="display: inline-block;">'
                            + parts[j] + '</code>');
            }
            return parts.join('<span style="color: #DDD;">/</span>');
        },
        isAttachmentProperty: function (value) {
            return value && value.indexOf("attachment:") === 0;
        },
        toTitleCase: function (str) {
            return (str
                .replace(/[_\/-]/g, ' ')
                .replace(/#/g, '')
            ).replace(/\w\S*/g, function (txt) {
                return txt.charAt(0).toUpperCase() + txt.substr(1).toLowerCase();
            });
        },
        /**
         * Enable autocomplete on the given jquery element with the given autocomplete
         * options.
         * @param $elem
         * @param options: Array of strings.
         */
        setUpAutocomplete: function($elem, options){
            if (!_.contains(options, $elem.value)) {
                options.unshift($elem.value);
            }
            $elem.$edit_view.select2({
                minimumInputLength: 0,
                delay: 0,
                data: {
                    results: _.map(options, function(o) {
                        return {
                            id: o,
                            text: o,
                        };
                    }),
                },
                // Allow manually entered text in drop down, which is not supported by legacy select2.
                createSearchChoice: function(term, data) {
                    if (!_.find(data, function(d) { return d.text === term; })) {
                        return {
                            id: term,
                            text: term,
                        };
                    }
                },
                escapeMarkup: function (m) { return DOMPurify.sanitize(m); },
                formatResult: function(result) {
                    var formatted = result.id;
                    if (module.CC_DETAIL_SCREEN.isAttachmentProperty(result.id)) {
                        formatted = (
                            '<i class="fa fa-paperclip"></i> ' +
                            result.id.substring(result.id.indexOf(":") + 1)
                        );
                    }
                    return DOMPurify.sanitize(formatted);
                },
            }).on('change', function() {
                $elem.val($elem.$edit_view.value);
                $elem.fire('change');
            });
            return $elem;
        }

    };

    // saveButton is a required parameter
    var SortRow = function(params){
        var self = this;
        params = params || {};

        self.textField = uiElement.input().val(typeof params.field !== 'undefined' ? params.field : "");
        module.CC_DETAIL_SCREEN.setUpAutocomplete(this.textField, params.properties);
        self.sortCalculation = ko.observable(typeof params.sortCalculation !== 'undefined' ? params.sortCalculation : "");

        self.showWarning = ko.observable(false);
        self.hasValidPropertyName = function(){
            return module.DetailScreenConfig.field_val_re.test(self.textField.val());
        };
        self.display = ko.observable(typeof params.display !== 'undefined' ? params.display : "");
        self.display.subscribe(function () {
            self.notifyButton();
        });
        self.toTitleCase = module.CC_DETAIL_SCREEN.toTitleCase;
        this.textField.on('change', function(){
            if (!self.hasValidPropertyName()){
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

        self.notifyButton = function(){
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
    };

    /**
     *
     * @param properties
     * @param saveButton
     * The button that should be activated when something changes
     * @constructor
     */
    var SortRows = function (properties, saveButton) {
        var self = this;
        self.sortRows = ko.observableArray([]);

        self.addSortRow = function (field, type, direction, blanks, display, notify, sortCalculation) {
            self.sortRows.push(new SortRow({
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

        self.showing = ko.computed(function(){
            return self.rowCount() > 0;
        });
    };

    var filterViewModel = function(filterText, saveButton) {
        var self = this;
        self.filterText = ko.observable(typeof filterText == "string" && filterText.length > 0 ? filterText : "");
        self.showing = ko.observable(self.filterText() !== "");

        self.filterText.subscribe(function(){
            saveButton.fire('change');
        });
        self.showing.subscribe(function(){
            saveButton.fire('change');
        });

        self.serialize = function(){
            if (self.showing()) {
                return self.filterText();
            }
            return null;
        };
    };

    module.ParentSelect = function (init) {
        var self = this;
        var defaultModule = _(init.parentModules).findWhere({is_parent: true});
        self.moduleId = ko.observable(init.moduleId || (defaultModule ? defaultModule.unique_id : null));
        self.active = ko.observable(init.active);
        self.parentModules = ko.observable(init.parentModules);
        self.lang = ko.observable(init.lang);
        self.langs = ko.observable(init.langs);
        function getTranslation(name, langs) {
            var firstLang = _(langs).find(function (lang) {
                return name[lang];
            });
            return name[firstLang];
        }
        self.moduleOptions = ko.computed(function () {
            return _(self.parentModules()).map(function (module) {
                var STAR = '\u2605', SPACE = '\u3000';
                var marker = (module.is_parent ? STAR : SPACE);
                return {
                    value: module.unique_id,
                    label: marker + ' ' + getTranslation(module.name, [self.lang()].concat(self.langs()))
                };
            });
        });
    };

    var FixtureSelect = function (init) {
        var self = this;
        self.active = ko.observable(init.active);
        self.fixtureType = ko.observable(init.fixtureType);
        self.displayColumn = ko.observable(init.displayColumn);
        self.localize = ko.observable(init.localize);
        self.variableColumn = ko.observable(init.variableColumn);
        self.xpath = ko.observable(init.xpath);
        self.fixture_columns = ko.computed(function() {
            var columns_for_type = init.fixture_columns_by_type[self.fixtureType()],
                default_option = [gettext("Select One")];
            return default_option.concat(columns_for_type);
        });
    };

    module.DetailScreenConfig = (function () {
        "use strict";

        function getPropertyTitle(property) {
            // Strip "<prefix>:" before converting to title case.
            // This is aimed at prefixes like ledger: and attachment:
            var i = property.indexOf(":");
            return module.CC_DETAIL_SCREEN.toTitleCase(property.substring(i + 1));
        }

        var DetailScreenConfig, Screen, Column, sortRows;
        var word = '[a-zA-Z][\\w_-]*';

        Column = (function () {
            function Column(col, screen) {
                /*
                    column properites: model, field, header, format
                    column extras: enum, late_flag
                */
                var that = this;
                hqImport("hqwebapp/js/main").eventize(this);
                this.original = JSON.parse(JSON.stringify(col));

                // Set defaults for normal (non-tab) column attributes
                var defaults = {
                    calc_xpath: ".",
                    enum: [],
                    field: "",
                    filter_xpath: "",
                    format: "plain",
                    graph_configuration: {},
                    hasAutocomplete: false,
                    header: {},
                    model: screen.model,
                    time_ago_interval: DetailScreenConfig.TIME_AGO.year,
                };
                _.each(_.keys(defaults), function(key) {
                    that.original[key] = that.original[key] || defaults[key];
                });
                this.original.late_flag = _.isNumber(this.original.late_flag) ? this.original.late_flag : 30;

                this.original.case_tile_field = ko.utils.unwrapObservable(this.original.case_tile_field) || "";
                this.case_tile_field = ko.observable(this.original.case_tile_field);

                // Set up tab attributes
                var tabDefaults = {
                    isTab: false,
                    hasNodeset: false,
                    nodeset: "",
                    relevant: "",
                };
                _.each(_.keys(tabDefaults), function(key) {
                    that.original[key] = that.original[key] || tabDefaults[key];
                });
                _.extend(this, _.pick(this.original, _.keys(tabDefaults)));

                this.screen = screen;
                this.lang = screen.lang;
                this.model = uiElement.select([
                    {label: "Case", value: "case"}
                ]).val(this.original.model);

                var icon = (module.CC_DETAIL_SCREEN.isAttachmentProperty(this.original.field)
                   ? 'fa fa-paperclip' : null);
                this.field = uiElement.input(this.original.field).setIcon(icon);

                // Make it possible to observe changes to this.field
                // note that observableVal is read only!
                // Writing to it will not update the value of the this.field text input
                this.field.observableVal = ko.observable(this.field.val());
                this.field.on("change", function(){
                    that.field.observableVal(that.field.val());
                });

                (function () {
                    var i, lang, visibleVal = "", invisibleVal = "", nodesetVal;
                    if (that.original.header && that.original.header[that.lang]) {
                        visibleVal = invisibleVal = that.original.header[that.lang];
                    } else {
                        for (i = 0; i < that.screen.langs.length; i += 1) {
                            lang = that.screen.langs[i];
                            if (that.original.header[lang]) {
                                visibleVal = that.original.header[lang]
                                    + hqImport('hqwebapp/js/ui_elements/ui-element-langcode-button').LANG_DELIN
                                    + lang;
                                break;
                            }
                        }
                    }
                    that.header = uiElement.input().val(invisibleVal);
                    that.header.setVisibleValue(visibleVal);

                    that.nodeset = uiElement.input().val(that.original.nodeset);
                    that.relevant = uiElement.input().val(that.original.relevant);
                    if (that.isTab) {
                        // hack to wait until the input's there to prepend the Tab: label.
                        setTimeout(function () {
                            that.header.ui.addClass('input-group').prepend($('<span class="input-group-addon">Tab</span>'));
                            that.nodeset.ui.addClass('input-group').prepend($('<span class="input-group-addon">Nodeset</span>'));
                            that.relevant.ui.addClass('input-group').prepend($('<span class="input-group-addon">Display Condition</span>'));
                        }, 0);

                        // Observe nodeset values for the sake of validation
                        if (that.hasNodeset) {
                            that.nodeset.observableVal = ko.observable(that.original.nodeset);
                            that.nodeset.on("change", function(){
                                that.nodeset.observableVal(that.nodeset.val());
                            });
                        }

                        if (that.original.relevant) {
                            that.relevant.observableVal = ko.observable(that.original.relevant);
                            that.relevant.on("change", function(){
                                that.relevant.observableVal(that.relevant.val());
                            });
                        }
                    }
                }());

                this.saveAttempted = ko.observable(false);
                var addOns = hqImport("hqwebapp/js/initial_page_data").get("add_ons");
                this.useXpathExpression = ko.observable(addOns.calc_xpaths && this.original.useXpathExpression);
                this.useXpathExpression.subscribe(function(){
                    that.fire('change');
                });
                this.showWarning = ko.computed(function() {
                    if(this.useXpathExpression()) {
                        return false;
                    }
                    if (this.isTab) {
                        // Data tab missing its nodeset
                        return this.hasNodeset && !this.nodeset.observableVal();
                    }
                    // Invalid property name
                    return (this.field.observableVal() || this.saveAttempted()) && !DetailScreenConfig.field_val_re.test(this.field.observableVal());
                }, this);

                // Add the graphing option if this is a graph so that we can set the value to graph
                var menuOptions = DetailScreenConfig.MENU_OPTIONS;
                if (this.original.format === "graph"){
                    menuOptions = menuOptions.concat([{value: "graph", label: ""}]);
                }

                this.format = uiElement.select(menuOptions).val(this.original.format || null);

                (function () {
                    var o = {
                        lang: that.lang,
                        langs: that.screen.langs,
                        module_id: that.screen.config.module_id,
                        items: that.original['enum'],
                        property_name: that.field,
                        multimedia: that.screen.config.multimedia,
                        values_are_icons: that.original.format == 'enum-image',
                        values_are_conditions: that.original.format === 'conditional-enum',
                    };
                    that.enum_extra = uiElement.key_value_mapping(o);
                }());
                var GraphConfigurationUiElement = hqImport('app_manager/js/details/graph_config').GraphConfigurationUiElement;
                this.graph_extra = new GraphConfigurationUiElement({
                    childCaseTypes: this.screen.childCaseTypes,
                    fixtures: this.screen.fixtures,
                    lang: this.lang,
                    langs: this.screen.langs,
                    name: this.header.val()
                }, this.original.graph_configuration);
                this.header.on("change", function(){
                    // The graph should always have the same name as the Column
                    that.graph_extra.setName(that.header.val());
                });

                this.late_flag_extra = uiElement.input().val(this.original.late_flag.toString());
                this.late_flag_extra.ui.find('input').css('width', 'auto').css("display", "inline-block");
                this.late_flag_extra.ui.prepend($('<span>' + gettext(' Days late ') + '</span>'));

                this.filter_xpath_extra = uiElement.input().val(this.original.filter_xpath.toString());
                this.filter_xpath_extra.ui.prepend($('<div/>'));

                this.calc_xpath_extra = uiElement.input().val(this.original.calc_xpath.toString());
                this.calc_xpath_extra.ui.prepend($('<div/>'));

                this.time_ago_extra = uiElement.select([
                    {label: gettext('Years since date'), value: DetailScreenConfig.TIME_AGO.year},
                    {label: gettext('Months since date'), value: DetailScreenConfig.TIME_AGO.month},
                    {label: gettext('Weeks since date'), value: DetailScreenConfig.TIME_AGO.week},
                    {label: gettext('Days since date'), value: DetailScreenConfig.TIME_AGO.day},
                    {label: gettext('Days until date'), value: -DetailScreenConfig.TIME_AGO.day},
                    {label: gettext('Weeks until date'), value: -DetailScreenConfig.TIME_AGO.week},
                    {label: gettext('Months until date'), value: -DetailScreenConfig.TIME_AGO.month}
                ]).val(this.original.time_ago_interval.toString());
                this.time_ago_extra.ui.prepend($('<div/>').text(gettext(' Measuring ')));

                function fireChange() {
                    that.fire('change');
                }
                _.each([
                    'model',
                    'field',
                    'header',
                    'nodeset',
                    'relevant',
                    'format',
                    'enum_extra',
                    'graph_extra',
                    'late_flag_extra',
                    'filter_xpath_extra',
                    'calc_xpath_extra',
                    'time_ago_extra'
                ], function(element) {
                    that[element].on('change', fireChange);
                });
                this.case_tile_field.subscribe(fireChange);

                this.$format = $('<div/>').append(this.format.ui);
                this.$format.find("select").css("margin-bottom", "5px");
                this.format.on('change', function () {
                    // Prevent this from running on page load before init
                    if (that.format.ui.parent().length > 0) {
                        that.enum_extra.ui.detach();
                        that.graph_extra.ui.detach();
                        that.late_flag_extra.ui.detach();
                        that.filter_xpath_extra.ui.detach();
                        that.calc_xpath_extra.ui.detach();
                        that.time_ago_extra.ui.detach();
                        if (this.val() === "enum" || this.val() === "enum-image" || this.val() === 'conditional-enum') {
                            that.enum_extra.values_are_icons(this.val() === 'enum-image');
                            that.enum_extra.values_are_conditions(this.val() === 'conditional-enum');
                            that.format.ui.parent().append(that.enum_extra.ui);
                        } else if (this.val() === "graph") {
                            // Replace format select with edit button
                            var parent = that.format.ui.parent();
                            parent.empty();
                            parent.append(that.graph_extra.ui);
                        } else if (this.val() === 'late-flag') {
                            that.format.ui.parent().append(that.late_flag_extra.ui);
                            var input = that.late_flag_extra.ui.find('input');
                            input.change(function() {
                                that.late_flag_extra.value = input.val();
                                fireChange();
                            });
                        } else if (this.val() === 'filter') {
                            that.format.ui.parent().append(that.filter_xpath_extra.ui);
                            var input = that.filter_xpath_extra.ui.find('input');
                            input.change(function() {
                                that.filter_xpath_extra.value = input.val();
                                fireChange();
                            });
                        } else if (this.val() === 'calculate') {
                            that.format.ui.parent().append(that.calc_xpath_extra.ui);
                            var input = that.calc_xpath_extra.ui.find('input');
                            input.change(function() {
                                that.calc_xpath_extra.value = input.val();
                                fireChange();
                            });
                        } else if (this.val() === 'time-ago') {
                            that.format.ui.parent().append(that.time_ago_extra.ui);
                            var select = that.time_ago_extra.ui.find('select');
                            select.change(function() {
                                that.time_ago_extra.value = select.val();
                                fireChange();
                            });
                        }
                    }
                }).fire('change');
                // Note that bind to the $edit_view for this google analytics event
                // (as opposed to the format object itself)
                // because this way the events are not fired during the initialization
                // of the page.
                this.format.$edit_view.on("change", function(event){
                    hqImport('analytix/js/google').track.event('Case List Config', 'Display Format', event.target.value);
                });
            }

            Column.init = function (col, screen) {
                return new Column(col, screen);
            };
            Column.prototype = {
                serialize: function () {
                    var column = this.original;
                    column.field = this.field.val();
                    column.header[this.lang] = this.header.val();
                    column.nodeset = this.nodeset.val();
                    column.relevant = this.relevant.val();
                    column.format = this.format.val();
                    column.enum = this.enum_extra.getItems();
                    column.graph_configuration =
                            this.format.val() == "graph" ? this.graph_extra.val() : null;
                    column.late_flag = parseInt(this.late_flag_extra.val(), 10);
                    column.time_ago_interval = parseFloat(this.time_ago_extra.val());
                    column.filter_xpath = this.filter_xpath_extra.val();
                    column.calc_xpath = this.calc_xpath_extra.val();
                    column.case_tile_field = this.case_tile_field();
                    if (this.isTab) {
                        // Note: starting_index is added by Screen.serialize
                        return _.extend({
                            starting_index: this.starting_index,
                            has_nodeset: column.hasNodeset,
                        }, _.pick(column, ['header', 'isTab', 'nodeset', 'relevant']));
                    }
                    return column;
                },
                setGrip: function (grip) {
                    this.grip = grip;
                },
                copyCallback: function () {
                    var column = this.serialize();
                    // add a marker that this is copied for this purpose
                    return JSON.stringify({
                        type: 'detail-screen-config:Column',
                        contents: column
                    });
                }
            };
            return Column;
        }());
        Screen = (function () {
            /**
             * The Screen "Class" is in charge inserting a table into the DOM that
             * contains rows for each case DetailColumn. It also handles the
             * reordering of these columns through drag and drop as well as
             * saving them on the server.
             * @param $home jQuery object where the Screen will be rendered
             * @param spec
             * @param config A DetailScreenConfig object.
             * @param options
             * @constructor
             */
            function Screen(spec, config, options) {
                var i, column, model, property, header,
                    that = this, columns;
                hqImport("hqwebapp/js/main").eventize(this);
                this.type = spec.type;
                this.saveUrl = options.saveUrl;
                this.config = config;
                this.columns = ko.observableArray([]);
                this.model = config.model;
                this.lang = options.lang;
                this.langs = options.langs || [];
                this.properties = options.properties;
                this.childCaseTypes = options.childCaseTypes;
                this.fixtures = options.fixtures;
                // The column key is used to retrieve the columns from the spec and
                // as the name of the key in the data object that is sent to the
                // server on save.
                this.columnKey = options.columnKey;
                // Not all Screen instances will handle sorting, parent selection,
                // and filtering. E.g The "Case Detail" tab only handles the module's
                // "long" case details. These flags will make sure this instance
                // doesn't try to save these configurations if it is not in charge
                // of these configurations.
                this.containsSortConfiguration = options.containsSortConfiguration;
                this.containsParentConfiguration = options.containsParentConfiguration;
                this.containsFixtureConfiguration = options.containsFixtureConfiguration;
                this.containsFilterConfiguration = options.containsFilterConfiguration;
                this.containsCaseListLookupConfiguration = options.containsCaseListLookupConfiguration;
                this.containsSearchConfiguration = options.containsSearchConfiguration;
                this.containsCustomXMLConfiguration = options.containsCustomXMLConfiguration;
                this.allowsTabs = options.allowsTabs;
                this.useCaseTiles = ko.observable(spec[this.columnKey].use_case_tiles ? "yes" : "no");
                this.showCaseTileColumn = ko.computed(function () {
                    return that.useCaseTiles() === "yes" && hqImport('hqwebapp/js/toggles').toggleEnabled('CASE_LIST_TILE');
                });
                this.persistCaseContext = ko.observable(spec[this.columnKey].persist_case_context || false);
                this.persistentCaseContextXML = ko.observable(spec[this.columnKey].persistent_case_context_xml|| 'case_name');
                this.customVariablesViewModel = {
                    enabled: hqImport('hqwebapp/js/toggles').toggleEnabled('CASE_LIST_CUSTOM_VARIABLES'),
                    xml: ko.observable(spec[this.columnKey].custom_variables || ""),
                };
                this.customVariablesViewModel.xml.subscribe(function(){
                    that.fireChange();
                });
                this.persistTileOnForms = ko.observable(spec[this.columnKey].persist_tile_on_forms || false);
                this.enableTilePullDown = ko.observable(spec[this.columnKey].pull_down_tile || false);
                this.allowsEmptyColumns = options.allowsEmptyColumns;
                this.persistentCaseTileFromModule = (
                    ko.observable(spec[this.columnKey].persistent_case_tile_from_module || ""));
                this.sortNodesetColumns = ko.observable(spec[this.columnKey].sort_nodeset_columns || false);
                this.fireChange = function() {
                    that.fire('change');
                };

                this.initColumnAsColumn = function (column) {
                    column.model.setEdit(false);
                    column.field.setEdit(true);
                    column.header.setEdit(true);
                    column.format.setEdit(true);
                    column.enum_extra.setEdit(true);
                    column.late_flag_extra.setEdit(true);
                    column.filter_xpath_extra.setEdit(true);
                    column.calc_xpath_extra.setEdit(true);
                    column.time_ago_extra.setEdit(true);
                    column.setGrip(true);
                    column.on('change', that.fireChange);

                    column.field.on('change', function () {
                        column.header.val(getPropertyTitle(this.val()));
                        column.header.fire("change");
                    });
                    if (column.original.hasAutocomplete || (
                        column.original.useXpathExpression && !column.useXpathExpression()
                    )) {
                        module.CC_DETAIL_SCREEN.setUpAutocomplete(column.field, that.properties);
                    }
                    return column;
                };

                columns = spec[this.columnKey].columns;
                // Inject tabs into the columns list:
                var tabs = spec[this.columnKey].tabs || [];
                for (i = 0; i < tabs.length; i++){
                    columns.splice(
                        tabs[i].starting_index + i,
                        0,
                        _.extend({
                            hasNodeset: tabs[i].has_nodeset,
                        }, _.pick(tabs[i], ["header", "nodeset", "isTab", "relevant"]))
                    );
                }
                if (this.columnKey === 'long') {
                    this.addTab = function(hasNodeset) {
                        var col = that.initColumnAsColumn(Column.init({
                            isTab: true,
                            hasNodeset: hasNodeset,
                            model: 'tab',
                        }, that));
                        that.columns.splice(0, 0, col);
                    };
                }

                // Filters are a type of DetailColumn on the server. Don't display
                // them with the other columns though
                columns = _.filter(columns, function(col){
                    return col.format != "filter";
                });

                // set up the columns
                for (i = 0; i < columns.length; i += 1) {
                    this.columns.push(Column.init(columns[i], this));
                    that.initColumnAsColumn(this.columns()[i]);
                }

                this.saveButton = hqImport("hqwebapp/js/main").initSaveButton({
                    unsavedMessage: gettext('You have unsaved detail screen configurations.'),
                    save: function () {
                        that.save();
                    }
                });
                this.on('change', function () {
                    this.saveButton.fire('change');
                });
                this.useCaseTiles.subscribe(function(){
                    that.saveButton.fire('change');
                });
                this.persistCaseContext.subscribe(function(){
                    that.saveButton.fire('change');
                });
                this.persistentCaseContextXML.subscribe(function(){
                    that.saveButton.fire('change');
                });
                this.persistTileOnForms.subscribe(function(){
                    that.saveButton.fire('change');
                });
                this.persistentCaseTileFromModule.subscribe(function(){
                    that.saveButton.fire('change');
                });
                this.enableTilePullDown.subscribe(function(){
                    that.saveButton.fire('change');
                });
                this.sortNodesetColumns.subscribe(function(){
                    that.saveButton.fire('change');
                });
                this.columns.subscribe(function () {
                    that.saveButton.fire('change');
                });
            }
            Screen.init = function (spec, config, options) {
                return new Screen(spec, config, options);
            };
            Screen.prototype = {
                save: function () {
                    var i;
                    //Only save if property names are valid
                    var containsTab = false;
                    var columns = this.columns();
                    for (i = 0; i < columns.length; i++){
                        var column = columns[i];
                        column.saveAttempted(true);
                        if (!column.isTab) {
                            if (column.showWarning()){
                                alert(gettext("There are errors in your property names"));
                                return;
                            }
                        } else {
                            if (column.showWarning()){
                                alert(gettext("There are errors in your tabs"));
                                return;
                            }
                            containsTab = true;
                        }
                    }
                    if (containsTab){
                        if (!columns[0].isTab) {
                            alert(gettext("All properties must be below a tab"));
                            return;
                        }
                    }

                    if (this.containsSortConfiguration) {
                        var sortRows = this.config.sortRows.sortRows();
                        for (i = 0; i < sortRows.length; i++) {
                            var row = sortRows[i];
                            if (!row.hasValidPropertyName()) {
                                row.showWarning(true);
                            }
                        }
                    }
                    if (this.validate()){
                        this.saveButton.ajax({
                            url: this.saveUrl,
                            type: "POST",
                            data: this.serialize(),
                            dataType: 'json',
                            success: function (data) {
                                var app_manager = hqImport('app_manager/js/app_manager');
                                app_manager.updateDOM(data.update);
                            }
                        });
                    }
                },
                validate: function(){
                    if (this.containsCaseListLookupConfiguration){
                        return this.config.caseListLookup.validate();
                    }
                    return true;
                },
                serialize: function () {
                    var columns = this.columns();
                    var data = {
                        type: JSON.stringify(this.type)
                    };

                    // Add columns
                    data[this.columnKey] = JSON.stringify(_.map(
                        _.filter(columns, function(c){return ! c.isTab;}),
                        function(c){return c.serialize();}
                    ));

                    // Add tabs
                    // calculate the starting index for each Tab
                    var acc = 0;
                    for (var j = 0; j < columns.length; j++) {
                        var c = columns[j];
                        if (c.isTab){
                            c.starting_index = acc;
                        } else {
                            acc++;
                        }
                    }
                    data.tabs = JSON.stringify(_.map(
                        _.filter(columns, function(c){return c.isTab;}),
                        function(c){return c.serialize();}
                    ));

                    data.useCaseTiles = this.useCaseTiles() === "yes" ? true : false;
                    data.persistCaseContext = this.persistCaseContext();
                    data.persistentCaseContextXML = this.persistentCaseContextXML();
                    data.persistTileOnForms = this.persistTileOnForms();
                    data.persistentCaseTileFromModule = this.persistentCaseTileFromModule();
                    data.enableTilePullDown = this.persistTileOnForms() ? this.enableTilePullDown() : false;
                    data.sortNodesetColumns = this.sortNodesetColumns() ? this.sortNodesetColumns() : false;

                    if (this.containsParentConfiguration) {
                        var parentSelect;
                        if (this.config.hasOwnProperty('parentSelect')) {
                            parentSelect = {
                                module_id: this.config.parentSelect.moduleId(),
                                relationship: 'parent',
                                active: this.config.parentSelect.active()
                            };
                        }
                        data.parent_select = JSON.stringify(parentSelect);
                    }
                    if (this.containsFixtureConfiguration) {
                        var fixtureSelect;
                        if (this.config.hasOwnProperty('fixtureSelect')) {
                            fixtureSelect = {
                                active: this.config.fixtureSelect.active(),
                                fixture_type: this.config.fixtureSelect.fixtureType(),
                                display_column: this.config.fixtureSelect.displayColumn(),
                                localize: this.config.fixtureSelect.localize(),
                                variable_column: this.config.fixtureSelect.variableColumn(),
                                xpath: this.config.fixtureSelect.xpath()
                            };
                        }
                        data.fixture_select = JSON.stringify(fixtureSelect);
                    }
                    if (this.containsSortConfiguration) {
                        data.sort_elements = JSON.stringify(_.map(this.config.sortRows.sortRows(), function(row){
                            return {
                                field: row.textField.val(),
                                type: row.type(),
                                direction: row.direction(),
                                blanks: row.blanks(),
                                display: row.display(),
                                sort_calculation: row.sortCalculation(),
                            };
                        }));
                    }
                    if (this.containsFilterConfiguration) {
                        data.filter = JSON.stringify(this.config.filter.serialize());
                    }
                    if (this.containsCaseListLookupConfiguration){
                        data.case_list_lookup = JSON.stringify(this.config.caseListLookup.serialize());
                    }
                    if (this.containsCustomXMLConfiguration){
                        data.custom_xml = this.config.customXMLViewModel.xml();
                    }
                    data[this.columnKey + '_custom_variables'] = this.customVariablesViewModel.xml();
                    if (this.containsSearchConfiguration) {
                        data.search_properties = JSON.stringify(this.config.search.serialize());
                    }
                    return data;
                },
                addItem: function (columnConfiguration, index) {
                    var column = this.initColumnAsColumn(
                        Column.init(columnConfiguration, this)
                    );
                    if (index === undefined) {
                        this.columns.push(column);
                    } else {
                        this.columns.splice(index, 0, column);
                    }
                    column.useXpathExpression(!!columnConfiguration.useXpathExpression);
                },
                pasteCallback: function (data, index) {
                    try {
                         data = JSON.parse(data);
                    } catch (e) {
                        // just ignore pasting non-json
                        return;
                    }
                    if (data.type === 'detail-screen-config:Column' && data.contents) {
                        this.addItem(data.contents, index);
                    }
                },
                addProperty: function () {
                    var type = this.columnKey === "short" ? "List" : "Detail";
                    hqImport('analytix/js/google').track.event('Case Management', 'Module Level Case ' + type, 'Add Property');
                    this.addItem({hasAutocomplete: true});
                },
                addCalculation: function () {
                    this.addItem({hasAutocomplete: false, format: 'calculate'});
                },
                addGraph: function () {
                    this.addItem({hasAutocomplete: false, format: 'graph'});
                },
                addXpathExpression: function () {
                    this.addItem({hasAutocomplete: false, useXpathExpression: true});
                }
            };
            return Screen;
        }());
        DetailScreenConfig = (function () {
            var DetailScreenConfig = function (spec) {
                var that = this;
                this.properties = spec.properties;
                this.screens = [];
                this.model = spec.model || 'case';
                this.lang = spec.lang;
                this.langs = spec.langs || [];
                this.multimedia = spec.multimedia || {};
                this.module_id = spec.module_id || '';
                if (spec.hasOwnProperty('parentSelect') && spec.parentSelect) {
                    this.parentSelect = new module.ParentSelect({
                        active: spec.parentSelect.active,
                        moduleId: spec.parentSelect.module_id,
                        parentModules: spec.parentModules,
                        lang: this.lang,
                        langs: this.langs
                    });
                }

                if (spec.hasOwnProperty('fixtureSelect') && spec.fixtureSelect) {
                    this.fixtureSelect = new FixtureSelect({
                        active: spec.fixtureSelect.active,
                        fixtureType: spec.fixtureSelect.fixture_type,
                        displayColumn: spec.fixtureSelect.display_column,
                        localize: spec.fixtureSelect.localize,
                        variableColumn: spec.fixtureSelect.variable_column,
                        xpath: spec.fixtureSelect.xpath,
                        fixture_columns_by_type: spec.fixture_columns_by_type,
                    });
                }
                this.saveUrl = spec.saveUrl;
                this.contextVariables = spec.contextVariables;

                /**
                 * Add a Screen to this DetailScreenConfig
                 * @param pair
                 * @param columnType
                 * The type of case properties that this Screen will be displaying,
                 * either "short" or "long".
                 */
                function addScreen(pair, columnType) {

                    var screen = Screen.init(
                        pair,
                        that,
                        {
                            lang: that.lang,
                            langs: that.langs,
                            properties: that.properties,
                            saveUrl: that.saveUrl,
                            columnKey: columnType,
                            childCaseTypes: spec.childCaseTypes,
                            fixtures: _.keys(spec.fixture_columns_by_type),
                            containsSortConfiguration: columnType == "short",
                            containsParentConfiguration: columnType == "short",
                            containsFixtureConfiguration: (columnType == "short" && hqImport('hqwebapp/js/toggles').toggleEnabled('FIXTURE_CASE_SELECTION')),
                            containsFilterConfiguration: columnType == "short",
                            containsCaseListLookupConfiguration: (columnType == "short" && hqImport('hqwebapp/js/toggles').toggleEnabled('CASE_LIST_LOOKUP')),
                            // TODO: Check case_search_enabled_for_domain(), not toggle. FB 225343
                            containsSearchConfiguration: (columnType === "short" && hqImport('hqwebapp/js/toggles').toggleEnabled('SYNC_SEARCH_CASE_CLAIM')),
                            containsCustomXMLConfiguration: columnType == "short",
                            allowsTabs: columnType == 'long',
                            allowsEmptyColumns: columnType == 'long'
                        }
                    );
                    that.screens.push(screen);
                    return screen;
                }

                if (spec.state.short !== undefined) {
                    this.shortScreen = addScreen(spec.state, "short");
                    // Set up filter
                    var filter_xpath = spec.state.short.filter;
                    this.filter = new filterViewModel(filter_xpath ? filter_xpath : null, this.shortScreen.saveButton);
                    // Set up SortRows
                    this.sortRows = new SortRows(this.properties, this.shortScreen.saveButton);
                    if (spec.sortRows) {
                        for (var j = 0; j < spec.sortRows.length; j++) {
                            this.sortRows.addSortRow(
                                spec.sortRows[j].field,
                                spec.sortRows[j].type,
                                spec.sortRows[j].direction,
                                spec.sortRows[j].blanks,
                                spec.sortRows[j].display[this.lang],
                                false,
                                spec.sortRows[j].sort_calculation
                            );
                        }
                    }
                    this.customXMLViewModel = {
                        enabled: hqImport('hqwebapp/js/toggles').toggleEnabled('CASE_LIST_CUSTOM_XML'),
                        xml: ko.observable(spec.state.short.custom_xml || "")
                    };
                    this.customXMLViewModel.xml.subscribe(function(v){
                        that.shortScreen.saveButton.fire("change");
                    });
                    var $case_list_lookup_el = $("#" + spec.state.type + "-list-callout-configuration");
                    this.caseListLookup = hqImport("app_manager/js/details/case_list_callout").caseListLookupViewModel(
                        $case_list_lookup_el,
                        spec.state.short,
                        spec.lang,
                        this.shortScreen.saveButton
                    );
                    // Set up case search
                    this.search = hqImport("app_manager/js/details/case_claim").searchViewModel(
                        spec.searchProperties || [],
                        spec.includeClosed,
                        spec.defaultProperties,
                        spec.lang,
                        spec.searchButtonDisplayCondition,
                        spec.blacklistedOwnerIdsExpression,
                        this.shortScreen.saveButton
                    );
                }
                if (spec.state.long !== undefined) {
                    var printModule = hqImport("app_manager/js/details/case_detail_print"),
                        printRef = printModule.getPrintRef(),
                        printTemplateUploader = printModule.getPrintTemplateUploader();
                    this.longScreen = addScreen(spec.state, "long");
                    this.printTemplateReference = _.extend(printRef, {
                        removePrintTemplate: function() {
                            $.post(
                                hqImport("hqwebapp/js/initial_page_data").reverse("hqmedia_remove_detail_print_template"),
                                {
                                    module_unique_id: spec.moduleUniqueId,
                                },
                                function(data, status) {
                                    if (status === 'success'){
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
            };
            DetailScreenConfig.init = function (spec) {
                return new DetailScreenConfig(spec);
            };
            return DetailScreenConfig;
        }());

        DetailScreenConfig.TIME_AGO = {
            year: 365.25,
            month: 365.25 / 12,
            week: 7,
            day: 1
        };

        DetailScreenConfig.MENU_OPTIONS = [
            {value: "plain", label: gettext('Plain')},
            {value: "date", label: gettext('Date')},
            {value: "time-ago", label: gettext('Time Since or Until Date')},
            {value: "phone", label: gettext('Phone Number')},
            {value: "enum", label: gettext('ID Mapping')},
            {value: "late-flag", label: gettext('Late Flag')},
            {value: "invisible", label: gettext('Search Only')},
            {value: "address", label: gettext('Address')},
            {value: "distance", label: gettext('Distance from current location')}
        ];

        if (hqImport('hqwebapp/js/toggles').toggleEnabled('MM_CASE_PROPERTIES')) {
            DetailScreenConfig.MENU_OPTIONS.push(
                {value: "picture", label: gettext('Picture')},
                {value: "audio", label: gettext('Audio')}
            );
        }

        var addOns = hqImport("hqwebapp/js/initial_page_data").get("add_ons");
        if (addOns.enum_image) {
            DetailScreenConfig.MENU_OPTIONS.push(
                {value: "enum-image", label: gettext('Icon')}
            );
        }
        if (addOns.conditional_enum) {
            DetailScreenConfig.MENU_OPTIONS.push(
                {value: "conditional-enum", label: gettext('Conditional ID Mapping')}
            );
        }
        if (addOns.calc_xpaths) {
            DetailScreenConfig.MENU_OPTIONS.push(
                {value: "calculate", label: gettext('Calculate')}
            );
        }

        DetailScreenConfig.field_format_warning_message = gettext("Must begin with a letter and contain only letters, numbers, '-', and '_'");

        DetailScreenConfig.field_val_re = new RegExp(
            '^(' + word + ':)*(' + word + '\\/)*#?' + word + '$'
        );

        return DetailScreenConfig;
    }());

    /* for sharing variables between essentially separate parts of the ui */
    module.state = {
        requires_case_details: ko.observable()
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
    }
};

ko.bindingHandlers.addSaveButtonListener = {
    init: function(element, valueAccessor, allBindings, viewModel, bindingContext){
        bindingContext.$parent.initSaveButtonListeners($(element).parent());
    }
};

// http://www.knockmeout.net/2011/05/dragging-dropping-and-sorting-with.html
// connect items with observableArrays
ko.bindingHandlers.sortableList = {
    init: function(element, valueAccessor) {
        var list = valueAccessor();
        $(element).sortable({
            handle: '.grip',
            cursor: 'move',
            update: function(event, ui) {
                //retrieve our actual data item
                var item = ko.dataFor(ui.item.get(0));
                //figure out its new position
                var position = ko.utils.arrayIndexOf(ui.item.parent().children(), ui.item[0]);
                //remove the item and add it back in the right spot
                if (position >= 0) {
                    list.remove(item);
                    list.splice(position, 0, item);
                }
                ui.item.remove();
                item.notifyButton();
            }
        });
    }
};
