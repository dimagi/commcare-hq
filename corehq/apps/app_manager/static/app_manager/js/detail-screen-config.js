/*globals $, _, uiElement, eventize, lcsMerge, COMMCAREHQ */

var CC_DETAIL_SCREEN = {
    getFieldHtml: function (field) {
        var text = field;
        if (CC_DETAIL_SCREEN.isAttachmentProperty(text)) {
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
                        + CC_DETAIL_SCREEN.toTitleCase(parts[j]) + '</span>');
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
     * @param options
     */
    setUpAutocomplete: function($elem, options){
        $elem.$edit_view.autocomplete({
            source: function (request, response) {
                var availableTags = _.map(options, function(value) {
                    var label = value;
                    if (CC_DETAIL_SCREEN.isAttachmentProperty(value)) {
                        label = (
                            '<span class="icon-paper-clip"></span> ' +
                            label.substring(label.indexOf(":") + 1)
                        );
                    }
                    return {value: value, label: label};
                });
                response(
                    $.ui.autocomplete.filter(availableTags, request.term)
                );
            },
            minLength: 0,
            delay: 0,
            select: function (event, ui) {
                $elem.val(ui.item.value);
                $elem.fire('change');
            }
        }).focus(function () {
            $(this).autocomplete('search');
        }).data("autocomplete")._renderItem = function (ul, item) {
            return $("<li></li>")
                .data("item.autocomplete", item)
                .append($("<a></a>").html(item.label))
                .appendTo(ul);
        };
        return $elem;
    }

};

// saveButton is a required parameter
var SortRow = function(params){
    var self = this;
    params = params || {};

    self.textField = uiElement.input().val(typeof params.field !== 'undefined' ? params.field : "");
    CC_DETAIL_SCREEN.setUpAutocomplete(this.textField, params.properties);

    self.showWarning = ko.observable(false);
    self.hasValidPropertyName = function(){
        return DetailScreenConfig.field_val_re.test(self.textField.val());
    };
    this.textField.on('change', function(){
        if (!self.hasValidPropertyName()){
            self.showWarning(true);
        } else {
            self.showWarning(false);
            self.notifyButton();
        }
    });

    self.type = ko.observable(typeof params.type !== 'undefined' ? params.type : "");
    self.type.subscribe(function () {
        self.notifyButton();
    });
    self.direction = ko.observable(typeof params.direction !== 'undefined' ? params.direction : "");
    self.direction.subscribe(function () {
        self.notifyButton();
    });

    self.notifyButton = function(){
        params.saveButton.fire('change');
    };

    self.ascendText = ko.computed(function () {
        var type = self.type();
        // This is here for the CACHE_AND_INDEX feature
        if (type === 'plain' || type === 'index') {
            return 'Increasing (a, b, c)';
        } else if (type === 'date') {
            return 'Increasing (May 1st, May 2nd)';
        } else if (type === 'int') {
            return 'Increasing (1, 2, 3)';
        } else if (type === 'double') {
            return 'Increasing (1.1, 1.2, 1.3)';
        }
    });

    self.descendText = ko.computed(function () {
        var type = self.type();
        if (type === 'plain' || type === 'index') {
            return 'Decreasing (c, b, a)';
        } else if (type === 'date') {
            return 'Decreasing (May 2nd, May 1st)'
        } else if (type === 'int') {
            return 'Decreasing (3, 2, 1)';
        } else if (type === 'double') {
            return 'Decreasing (1.3, 1.2, 1.1)';
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

    self.addSortRow = function (field, type, direction, notify) {
        self.sortRows.push(new SortRow({
            field: field,
            type: type,
            direction: direction,
            saveButton: saveButton,
            properties: properties
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

var filterViewModel = function(filterText, saveButton){
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

function ParentSelect(init) {
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
}

var DetailScreenConfig = (function () {
    "use strict";

    function getPropertyTitle(property) {
        // Strip "<prefix>:" before converting to title case.
        // This is aimed at prefixes like ledger: and attachment:
        var i = property.indexOf(":");
        return CC_DETAIL_SCREEN.toTitleCase(property.substring(i + 1));
    }

    var DetailScreenConfig, Screen, Column, sortRows;
    var word = '[a-zA-Z][\\w_-]*';

    Column = (function () {
        function Column(col, screen) {
            /*
                column properites: model, field, header, format
                column extras: enum, late_flag
            */
            var that = this, elements, i;
            eventize(this);
            this.original = JSON.parse(JSON.stringify(col));

            function orDefault(value, d) {
                if (value === undefined) {
                    return d;
                } else {
                    return value;
                }
            }
            this.original.model = this.original.model || screen.model;
            this.original.field = this.original.field || "";
            this.original.hasAutocomplete = orDefault(this.original.hasAutocomplete, true);
            this.original.header = this.original.header || {};
            this.original.format = this.original.format || "plain";
            this.original['enum'] = this.original['enum'] || [];
            this.original.late_flag = _.isNumber(this.original.late_flag) ? this.original.late_flag : 30;
            this.original.filter_xpath = this.original.filter_xpath || "";
            this.original.calc_xpath = this.original.calc_xpath || ".";
            this.original.graph_configuration = this.original.graph_configuration || {};
            this.original.case_tile_field = ko.utils.unwrapObservable(this.original.case_tile_field) || "";

            // Tab attributes
            this.original.isTab = this.original.isTab !== undefined ? this.original.isTab : false;
            this.isTab = this.original.isTab;

            this.case_tile_field = ko.observable(this.original.case_tile_field);


            this.original.time_ago_interval = this.original.time_ago_interval || DetailScreenConfig.TIME_AGO.year;

            this.screen = screen;
            this.lang = screen.lang;

            this.model = uiElement.select([
                {label: "Case", value: "case"}
            ]).val(this.original.model);

            var icon = (CC_DETAIL_SCREEN.isAttachmentProperty(this.original.field)
               ? COMMCAREHQ.icons.PAPERCLIP : null);
            this.field = uiElement.input().val(this.original.field).setIcon(icon);

            // Make it possible to observe changes to this.field
            // note that observableVal is read only!
            // Writing to it will not update the value of the this.field text input
            this.field.observableVal = ko.observable(this.field.val());
            this.field.on("change", function(){
                that.field.observableVal(that.field.val());
            });

            this.saveAttempted = ko.observable(false);
            this.showWarning = ko.computed(function() {
                // True if an invalid property name warning should be displayed.
                return (this.field.observableVal() || this.saveAttempted()) && !DetailScreenConfig.field_val_re.test(this.field.observableVal());
            }, this);

            (function () {
                var i, lang, visibleVal = "", invisibleVal = "";
                if (that.original.header && that.original.header[that.lang]) {
                    visibleVal = invisibleVal = that.original.header[that.lang];
                } else {
                    for (i = 0; i < that.screen.langs.length; i += 1) {
                        lang = that.screen.langs[i];
                        if (that.original.header[lang]) {
                            visibleVal = that.original.header[lang] + langcodeTag.LANG_DELIN + lang;
                            break;
                        }
                    }
                }
                that.header = uiElement.input().val(invisibleVal);
                that.header.setVisibleValue(visibleVal);
                if (that.isTab) {
                    // hack to wait until the input's there to prepend the Tab: label.
                    setTimeout(function () {
                        that.header.ui.addClass('input-prepend').prepend($('<span class="add-on">Tab:</span>'));
                    }, 0);
                }
            }());

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
                    items: that.original['enum'],
                    modalTitle: 'Editing mapping for ' + that.original.field
                };
                that.enum_extra = uiElement.key_value_mapping(o);
            }());

            this.graph_extra = new uiElement.GraphConfiguration({
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
            this.late_flag_extra.ui.find('input').css('width', 'auto');
            this.late_flag_extra.ui.prepend(
                $('<span/>').css('float', 'left')
                            .css('padding', '5px 5px 0px 0px')
                            .text(DetailScreenConfig.message.LATE_FLAG_EXTRA_LABEL));

            this.filter_xpath_extra = uiElement.input().val(this.original.filter_xpath.toString());
            this.filter_xpath_extra.ui.prepend($('<div/>').text(DetailScreenConfig.message.FILTER_XPATH_EXTRA_LABEL));

            this.calc_xpath_extra = uiElement.input().val(this.original.calc_xpath.toString());
            this.calc_xpath_extra.ui.prepend($('<div/>').text(DetailScreenConfig.message.CALC_XPATH_EXTRA_LABEL));


            this.time_ago_extra = uiElement.select([
                {label: DetailScreenConfig.message.TIME_AGO_INTERVAL.YEARS, value: DetailScreenConfig.TIME_AGO.year},
                {label: DetailScreenConfig.message.TIME_AGO_INTERVAL.MONTHS, value: DetailScreenConfig.TIME_AGO.month},
                {label: DetailScreenConfig.message.TIME_AGO_INTERVAL.WEEKS, value: DetailScreenConfig.TIME_AGO.week},
                {label: DetailScreenConfig.message.TIME_AGO_INTERVAL.DAYS, value: DetailScreenConfig.TIME_AGO.day},
                {label: DetailScreenConfig.message.TIME_AGO_INTERVAL.DAYS_UNTIL, value: -DetailScreenConfig.TIME_AGO.day},
                {label: DetailScreenConfig.message.TIME_AGO_INTERVAL.WEEKS_UNTIL, value: -DetailScreenConfig.TIME_AGO.week},
                {label: DetailScreenConfig.message.TIME_AGO_INTERVAL.MONTHS_UNTIL, value: -DetailScreenConfig.TIME_AGO.month}
            ]).val(this.original.time_ago_interval.toString());
            this.time_ago_extra.ui.prepend($('<div/>').text(DetailScreenConfig.message.TIME_AGO_EXTRA_LABEL));

            elements = [
                'model',
                'field',
                'header',
                'format',
                'enum_extra',
                'graph_extra',
                'late_flag_extra',
                'filter_xpath_extra',
                'calc_xpath_extra',
                'time_ago_extra'
            ];

            function fireChange() {
                that.fire('change');
            }

            for (i = 0; i < elements.length; i += 1) {
                this[elements[i]].on('change', fireChange);
            }
            this.case_tile_field.subscribe(fireChange);

            this.$format = $('<div/>').append(this.format.ui);
            this.format.on('change', function () {
                // Prevent this from running on page load before init
                if (that.format.ui.parent().length > 0) {
                    that.enum_extra.ui.detach();
                    that.graph_extra.ui.detach();
                    that.late_flag_extra.ui.detach();
                    that.filter_xpath_extra.ui.detach();
                    that.calc_xpath_extra.ui.detach();
                    that.time_ago_extra.ui.detach();

                    if (this.val() === "enum" || this.val() === "enum-image") {
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
                ga_track_event('Case List Config', 'Display Format', event.target.value);
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
                    return {
                        starting_index: this.starting_index,
                        header: column.header,
                        isTab: true
                    };
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
            eventize(this);
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
            // The column key is used to retreive the columns from the spec and
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
            this.containsFilterConfiguration = options.containsFilterConfiguration;
            this.containsCustomXMLConfiguration = options.containsCustomXMLConfiguration;
            this.allowsTabs = options.allowsTabs;
            this.useCaseTiles = ko.observable(spec[this.columnKey].use_case_tiles ? "yes" : "no");
            this.persistTileOnForms = ko.observable(spec[this.columnKey].persist_tile_on_forms || false);
            this.enableTilePullDown = ko.observable(spec[this.columnKey].pull_down_tile || false);
            this.allowsEmptyColumns = options.allowsEmptyColumns;

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
                if (column.original.hasAutocomplete) {
                    CC_DETAIL_SCREEN.setUpAutocomplete(column.field, that.properties);
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
                    {isTab: true, header: tabs[i].header}
                );
            }
            if (this.columnKey === 'long') {
                this.addTab = function() {
                    var col = that.initColumnAsColumn(Column.init({
                        isTab: true,
                        model: 'tab'
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

            this.saveButton = COMMCAREHQ.SaveButton.init({
                unsavedMessage: DetailScreenConfig.message.UNSAVED_MESSAGE,
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
            this.persistTileOnForms.subscribe(function(){
                that.saveButton.fire('change');
            });
            this.enableTilePullDown.subscribe(function(){
                that.saveButton.fire('change');
            });
            ko.computed(function () {
                that.columns();
            }).subscribe(function () {
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
                            alert("There are errors in your property names");
                            return;
                        }
                    } else {
                        containsTab = true;
                    }
                }
                if (containsTab){
                    if (!columns[0].isTab) {
                        alert("All properties must be below a tab");
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

                this.saveButton.ajax({
                    url: this.saveUrl,
                    type: "POST",
                    data: this.serialize(),
                    dataType: 'json',
                    success: function (data) {
                        COMMCAREHQ.app_manager.updateDOM(data.update);
                    }
                });
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

                data.useCaseTiles = this.useCaseTiles() == "yes" ? true : false;
                data.persistTileOnForms = this.persistTileOnForms();
                data.enableTilePullDown = this.persistTileOnForms() ? this.enableTilePullDown() : false;

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
                if (this.containsSortConfiguration) {
                    data.sort_elements = JSON.stringify(_.map(this.config.sortRows.sortRows(), function(row){
                        return {
                            field: row.textField.val(),
                            type: row.type(),
                            direction: row.direction()
                        };
                    }));
                }
                if (this.containsFilterConfiguration) {
                    data.filter = JSON.stringify(this.config.filter.serialize());
                }
                if (this.containsCustomXMLConfiguration){
                    data.custom_xml = this.config.customXMLViewModel.xml();
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
                this.addItem({hasAutocomplete: true});
            },
            addCalculation: function () {
                this.addItem({hasAutocomplete: false, format: 'calculate'});
            },
            addGraph: function () {
                this.addItem({hasAutocomplete: false, format: 'graph'});
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
            if (spec.hasOwnProperty('parentSelect') && spec.parentSelect) {
                this.parentSelect = new ParentSelect({
                    active: spec.parentSelect.active,
                    moduleId: spec.parentSelect.module_id,
                    parentModules: spec.parentModules,
                    lang: this.lang,
                    langs: this.langs
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
                        fixtures: spec.fixtures,
                        containsSortConfiguration: columnType == "short",
                        containsParentConfiguration: columnType == "short",
                        containsFilterConfiguration: columnType == "short",
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
                            false
                        );
                    }
                }
                this.customXMLViewModel = {
                    enabled: window.toggles.CASE_LIST_CUSTOM_XML,
                    xml: ko.observable(spec.state.short.custom_xml || "")
                };
                this.customXMLViewModel.xml.subscribe(function(v){
                    that.shortScreen.saveButton.fire("change");
                });
            }
            if (spec.state.long !== undefined) {
                this.longScreen = addScreen(spec.state, "long");
            }
        };
        DetailScreenConfig.init = function (spec) {
            return new DetailScreenConfig(spec);
        };
        return DetailScreenConfig;
    }());

    DetailScreenConfig.message = {

        MODEL: 'Model',
        FIELD: 'Property',
        HEADER: 'Display Text',
        FORMAT: 'Format',

        PLAIN_FORMAT: 'Plain',
        DATE_FORMAT: 'Date',
        TIME_AGO_FORMAT: 'Time Since or Until Date',
        TIME_AGO_EXTRA_LABEL: ' Measuring: ',
        TIME_AGO_INTERVAL: {
            YEARS: 'Years since date',
            MONTHS: 'Months since date',
            WEEKS: 'Weeks since date',
            DAYS: 'Days since date',
            DAYS_UNTIL: 'Days until date',
            WEEKS_UNTIL: 'Weeks until date',
            MONTHS_UNTIL: 'Months until date'
        },
        PHONE_FORMAT: 'Phone Number',
        ENUM_FORMAT: 'ID Mapping',
        ENUM_IMAGE_FORMAT: 'Icon',
        ENUM_EXTRA_LABEL: 'Mapping: ',
        LATE_FLAG_FORMAT: 'Late Flag',
        LATE_FLAG_EXTRA_LABEL: 'Days late: ',
        FILTER_XPATH_EXTRA_LABEL: '',
        INVISIBLE_FORMAT: 'Search Only',
        ADDRESS_FORMAT: 'Address (Android/CloudCare)',
        PICTURE_FORMAT: 'Picture',
        AUDIO_FORMAT: 'Audio',
        CALC_XPATH_FORMAT: 'Calculate',
        CALC_XPATH_EXTRA_LABEL: '',

        ADD_COLUMN: 'Add to list',
        COPY_COLUMN: 'Duplicate',
        DELETE_COLUMN: 'Delete',

        UNSAVED_MESSAGE: 'You have unsaved detail screen configurations.'
    };

    DetailScreenConfig.TIME_AGO = {
        year: 365.25,
        month: 365.25 / 12,
        week: 7,
        day: 1
    };

    DetailScreenConfig.MENU_OPTIONS = [
        {value: "plain", label: DetailScreenConfig.message.PLAIN_FORMAT},
        {value: "date", label: DetailScreenConfig.message.DATE_FORMAT},
        {value: "time-ago", label: DetailScreenConfig.message.TIME_AGO_FORMAT},
        {value: "phone", label: DetailScreenConfig.message.PHONE_FORMAT},
        {value: "enum", label: DetailScreenConfig.message.ENUM_FORMAT},
        {value: "late-flag", label: DetailScreenConfig.message.LATE_FLAG_FORMAT},
        {value: "invisible", label: DetailScreenConfig.message.INVISIBLE_FORMAT},
        {value: "address", label: DetailScreenConfig.message.ADDRESS_FORMAT}
    ];

    if (window.toggles.MM_CASE_PROPERTIES) {
        DetailScreenConfig.MENU_OPTIONS.push(
            {value: "picture", label: DetailScreenConfig.message.PICTURE_FORMAT},
            {value: "audio", label: DetailScreenConfig.message.AUDIO_FORMAT}
        );
    }

    if (window.feature_previews.ENUM_IMAGE) {
        DetailScreenConfig.MENU_OPTIONS.push(
            {value: "enum-image", label: DetailScreenConfig.message.ENUM_IMAGE_FORMAT + ' (Preview!)'}
        );
    }

    if (window.feature_previews.CALC_XPATHS) {
        DetailScreenConfig.MENU_OPTIONS.push(
            {value: "calculate", label: DetailScreenConfig.message.CALC_XPATH_FORMAT + ' (Preview!)'}
        );
    }
    DetailScreenConfig.field_format_warning_message = "Must begin with a letter and contain only letters, numbers, '-', and '_'";

    DetailScreenConfig.field_val_re = new RegExp(
        '^(' + word + ':)*(' + word + '\\/)*#?' + word + '$'
    );

    return DetailScreenConfig;
}());


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
