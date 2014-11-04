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

/**
 * A custom knockout binding that replaces the element's contents with a jquery
 * element.
 * @type {{update: update}}
 */
ko.bindingHandlers.jqueryElement = {
    update: function(element, valueAccessor, allBindings, viewModel, bindingContext) {
        $(element).empty();
        $(element).append(ko.unwrap(valueAccessor()));
    }
};

var SortRow = function(params){
    var self = this;
    params = params || {};
    self.notifyButtonOfChanges =
            typeof params.notifyButtonOfChanges !== 'undefined' ? params.notifyButtonOfChanges : true;
    self.field = ko.observable(typeof params.field !== 'undefined' ? params.field : "");
    self.type = ko.observable(typeof params.type !== 'undefined' ? params.type : "");
    self.direction = ko.observable(typeof params.direction !== 'undefined' ? params.direction : "");

    if (self.notifyButtonOfChanges) {
        self.type.subscribe(function () {
            window.sortRowSaveButton.fire('change');
        });
        self.direction.subscribe(function () {
            window.sortRowSaveButton.fire('change');
        });
    }

    self.fieldHtml = ko.computed(function () {
        return CC_DETAIL_SCREEN.getFieldHtml(self.field());
    });

    self.ascendText = ko.computed(function () {
        var type = self.type();
        if (type === 'plain') {
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
        if (type === 'plain') {
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
var SortRowTemplate = function(params){
    var self = this;
    params = params || {};
    self.textField = uiElement.input().val("");
    CC_DETAIL_SCREEN.setUpAutocomplete(this.textField, params.properties);

    self.showWarning = ko.observable(false);
    self.warningElement = DetailScreenConfig.field_format_warning.clone().show();
    self.hasValidPropertyName = function(){
        return DetailScreenConfig.field_val_re.test(self.textField.val());
    };
    this.textField.on('change', function(){
        if (!self.hasValidPropertyName()){
            self.showWarning(true);
        } else {
            self.showWarning(false);
        }
    });
};
SortRowTemplate.prototype = new SortRow({notifyButtonOfChanges: false});

/**
 *
 * @param properties
 * @param edit is true if the user has permissions to edit the sort rows.
 * @constructor
 */
var SortRows = function (properties, edit) {
    var self = this;
    self.addButtonClicked = ko.observable(false);
    self.sortRows = ko.observableArray([]);
    if (edit) {
        self.templateRow = new SortRowTemplate({properties: properties});
    } else {
        self.templateRow = []; // Empty list because sortRows.concat([]) == sortRows
    }

    self.addSortRow = function (field, type, direction) {
        self.sortRows.push(new SortRow({
            field: field,
            type: type,
            direction: direction
        }));
    };
    self.addSortRowFromTemplateRow = function(row) {
        if (! row.hasValidPropertyName()){
            // row won't have format_warning showing if it's empty
            row.showWarning(true);
            return;
        }
        self.sortRows.push(new SortRow({
            field: row.textField.val(),
            type: row.type(),
            direction: row.direction()
        }));
        row.textField.val("");
        window.sortRowSaveButton.fire('change');
    };
    self.removeSortRow = function (row) {
        self.sortRows.remove(row);
        window.sortRowSaveButton.fire('change');
    };

    self.rowCount = ko.computed(function () {
        return self.sortRows().length;
    });

    self.showing = ko.computed(function(){
        return self.addButtonClicked() || self.rowCount() > 0;
    });
};

var filterViewModel = function(filterText){
    var self = this;
    self.filterText = ko.observable(typeof filterText == "string" && filterText.length > 0 ? filterText : "");
    self.showing = ko.observable(self.filterText() !== "");

    self.filterText.subscribe(function(){
        window.filterSaveButton.fire('change');
    });
    self.showing.subscribe(function(){
        window.filterSaveButton.fire('change');
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
                window.sortRowSaveButton.fire('change');
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
            var icon = (CC_DETAIL_SCREEN.isAttachmentProperty(this.original.field)
                           ? COMMCAREHQ.icons.PAPERCLIP : null);

            this.original.time_ago_interval = this.original.time_ago_interval || DetailScreenConfig.TIME_AGO.year;

            this.screen = screen;
            this.lang = screen.lang;

            this.model = uiElement.select([
                {label: "Case", value: "case"}
            ]).val(this.original.model);
            this.field = uiElement.input().val(this.original.field).setIcon(icon);
            this.format_warning = DetailScreenConfig.field_format_warning.clone().hide();

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
            }());
            this.format = uiElement.select(DetailScreenConfig.MENU_OPTIONS).val(this.original.format || null);

            (function () {
                var o = {
                    lang: that.lang,
                    langs: that.screen.langs,
                    items: that.original['enum'],
                    modalTitle: 'Editing mapping for ' + that.original.field
                };
                that.enum_extra = uiElement.key_value_mapping(o);
            }());
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

            this.format.on('change', function () {
                // Prevent this from running on page load before init
                if (that.format.ui.parent().length > 0) {
                    that.enum_extra.ui.detach();
                    that.late_flag_extra.ui.detach();
                    that.filter_xpath_extra.ui.detach();
                    that.calc_xpath_extra.ui.detach();
                    that.time_ago_extra.ui.detach();

                    if (this.val() === "enum" || this.val() === "enum-image") {
                        that.format.ui.parent().append(that.enum_extra.ui);
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

            this.$delete = $('<i></i>').addClass(COMMCAREHQ.icons.DELETE).click(function () {
                $(this).remove();
                that.screen.fire('delete-column', that);
            }).css({cursor: 'pointer'}).attr('title', DetailScreenConfig.message.DELETE_COLUMN);
        }

        Column.init = function (col, screen) {
            return new Column(col, screen);
        };
        Column.prototype = {
            duplicate: function () {
                this.screen.fire('add-column', this);
            },
            serialize: function () {
                var column = this.original;
                column.field = this.field.val();
                column.header[this.lang] = this.header.val();
                column.format = this.format.val();
                column['enum'] = this.enum_extra.getItems();
                column.late_flag = parseInt(this.late_flag_extra.val(), 10);
                column.time_ago_interval = parseFloat(this.time_ago_extra.val());
                column.filter_xpath = this.filter_xpath_extra.val();
                column.calc_xpath = this.calc_xpath_extra.val();
                return column;
            },
            setGrip: function (grip) {
                if (this.grip !== grip) {
                    this.grip = grip;
                    if (grip) {
                        this.$grip = $('<i class="grip"></i>').addClass(COMMCAREHQ.icons.GRIP).css({
                            cursor: 'move'
                        }).mousedown(function () {
                            $(':focus').blur();
                        });
                    } else {
                        this.$grip = $('<span class="sort-disabled"></span>');
                    }
                }
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
        function Screen($home, spec, config, options) {
            var i, column, model, property, header,
                that = this, columns;
            eventize(this);
            this.type = spec.type;
            this.saveUrl = options.saveUrl;
            this.$home = $home;
            // $location is the element containing this Screen.
            this.$location = options.$location;
            this.config = config;
            this.edit = options.edit;
            this.columns = [];
            this.model = config.model;
            this.lang = options.lang;
            this.langs = options.langs || [];
            this.properties = options.properties;
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

            this.fireChange = function() {
                that.fire('change');
            };

            this.initColumnAsColumn = function (column) {
                column.model.setEdit(false);
                column.field.setEdit(that.edit);
                column.header.setEdit(that.edit);
                column.format.setEdit(that.edit);
                column.enum_extra.setEdit(that.edit);
                column.late_flag_extra.setEdit(that.edit);
                column.filter_xpath_extra.setEdit(that.edit);
                column.calc_xpath_extra.setEdit(that.edit);
                column.time_ago_extra.setEdit(that.edit);
                column.setGrip(true);
                column.on('change', that.fireChange);

                column.field.on('change', function () {
                    column.header.val(getPropertyTitle(this.val()));
                    if (this.val() && !DetailScreenConfig.field_val_re.test(this.val())) {
                        column.format_warning.show().parent().addClass('error');
                    } else {
                        column.format_warning.hide().parent().removeClass('error');
                    }
                });
                if (column.original.hasAutocomplete) {
                    CC_DETAIL_SCREEN.setUpAutocomplete(column.field, that.properties);
                }
                return column;
            };

            columns = spec[this.columnKey].columns;

            // Filters are a type of DetailColumn on the server. Don't display
            // them with the other columns though
            columns = _.filter(columns, function(col){
                return col.format != "filter";
            });

            // set up the columns
            for (i = 0; i < columns.length; i += 1) {
                this.columns[i] = Column.init(columns[i], this);
                that.initColumnAsColumn(this.columns[i]);
            }

            this.saveButton = COMMCAREHQ.SaveButton.init({
                unsavedMessage: DetailScreenConfig.message.UNSAVED_MESSAGE,
                save: function () {
                    that.save();
                }
            });

            if (this.containsSortConfiguration){
                window.sortRowSaveButton = this.saveButton;
            }
            if (this.containsFilterConfiguration){
                window.filterSaveButton = this.saveButton;
            }

            this.render();
            this.on('add-column', function (column) {
                var i, ii, $tr;
                i = this.columns.indexOf(column);
                if (i === -1) {
                    ii = -1;
                    for (i = 0; i < this.columns.length; i += 1) {
                        if (column.model.val() === this.columns[i].model.val() &&
                                column.field.val() === this.columns[i].field.val()) {
                            ii = i;
                        }
                    }
                    i = ii;
                }
                column = column.serialize(true);
                column = Column.init(column, this);
                that.initColumnAsColumn(column);
                if (i !== -1) {
                    this.columns.splice(i + 1, 0, column);
                } else {
                    this.columns.push(column);
                }
                $tr = this.addColumn(column, this.$columns, this.$columns.length);
                if (i !== -1) {
                    $tr.detach().insertAfter(this.$columns.find('tr:nth-child(' + (i + 1).toString() + ')'));
                }
                $tr.hide().fadeIn('slow');
                this.fire('change');
            });
            this.on('delete-column', function (column) {
                var i = this.columns.indexOf(column);
                this.$columns.find('tr:nth-child(' + (i + 1).toString() + ')').fadeOut('slow', function () {
                    $(this).remove();
                });
                this.columns.splice(i, 1);
                this.fire('change');
            });
            this.on('change', function () {
                this.saveButton.fire('change');
                this.$columns.find('tr').each(function (i) {
                    $(this).data('index', i);
                });
            });
        }
        Screen.init = function ($home, spec, config, options) {
            return new Screen($home, spec, config, options);
        };
        Screen.prototype = {
            save: function () {
                //Only save if property names are valid
                for (var i = 0; i < this.columns.length; i++){
                    var column = this.columns[i];
                    if (! DetailScreenConfig.field_val_re.test(column.field.val())){
                        // column won't have format_warning showing if it's empty
                        column.format_warning.show().parent().addClass('error');
                        alert("There are errors in your property names");
                        return;
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
                var data = {
                    type: JSON.stringify(this.type)
                };
                data[this.columnKey] = JSON.stringify(_.map(this.columns, function(c){return c.serialize();}));

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
                    data.sort_elements = JSON.stringify(ko.toJS(this.config.sortRows.sortRows));
                }
                if (this.containsFilterConfiguration) {
                    data.filter = JSON.stringify(this.config.filter.serialize());
                }
                return data;
            },
            addColumn: function (column, $tbody, i) {
                var $tr = $('<tr/>').data('index', i).appendTo($tbody);
                if (this.edit) {
                    $('<td/>').addClass('detail-screen-icon').append(column.$grip).appendTo($tr);
                } else {
                    $('<td/>').addClass('detail-screen-icon').appendTo($tr);
                }

                if (!column.field.edit) {
                    column.field.setHtml(CC_DETAIL_SCREEN.getFieldHtml(column.field.val()));
                }
                var dsf = $('<td/>').addClass('detail-screen-field control-group').append(column.field.ui);
                dsf.append(column.format_warning);
                if (column.field.value && !DetailScreenConfig.field_val_re.test(column.field.value)) {
                    column.format_warning.show().parent().addClass('error');
                }
                dsf.appendTo($tr);

                $('<td/>').addClass('detail-screen-header').append(column.header.ui).appendTo($tr);
                $('<td/>').addClass('detail-screen-format').append(column.format.ui).appendTo($tr);
                column.format.fire('change');

                if (this.edit) {
                    $('<td/>').addClass('detail-screen-icon').append(
                        column.$delete
                    ).appendTo($tr);
                } else {
                    $('<td/>').addClass('detail-screen-icon').appendTo($tr);
                }
                return $tr;
            },
            render: function () {
                var that = this;
                var $table, $columns, $thead, $tr, i, $box, $buttonRow, $addButton;

                this.$home.empty();
                $box = $("<div/>").appendTo(this.$home);

                // this is a not-so-elegant way to get the styling right
                COMMCAREHQ.initBlock(this.$home);

                function getDuplicateCallback(column) {
                    return function (e) {
                        column.duplicate();
                    };
                }
                if (!this.edit && _.isEmpty(this.columns)) {
                    $('<p/>').text(DetailScreenConfig.message.EMPTY_SCREEN).appendTo($box);
                } else {
                    if (this.edit) {
                        if (window.enableNewSort) {

                            // $location id is in this form: "-detail-screen-config"
                            // so $detailBody id will be in this form: "-detail-screen-config-body"
                            var $detailBody = $("#" + this.$location.attr("id") + "-body");

                            $('<div id="saveBtn" class="clearfix">')
                                .append(this.saveButton.ui)
                                .prependTo($detailBody);
                        } else {
                            $('<div class="clearfix">')
                                .append(this.saveButton.ui)
                                .prependTo($box);
                        }
                    }
                    this.$columns = $('</tbody>');

                    // Add the "Add Property" button

                    var buttonDropdownItems = [
                        $('<li class="add-property-item"><a>Property</a></li>')
                    ];
                    if (this.config.calculationEnabled){
                        buttonDropdownItems.push(
                            $('<li class="add-calculation-item"><a>Calculation</a></li>')
                        );
                    }
                    $addButton = $(
                        '<div class="btn-group">' +
                            '<button class="btn add-property-item">Add Property</button>' +
                        '</div>'
                    );
                    if (buttonDropdownItems.length > 1){
                        // Add the caret
                        $addButton.append($(
                            '<button class="btn dropdown-toggle" data-toggle="dropdown">' +
                                '<span class="caret"></span>' +
                            '</button>'
                        ));
                        // Add the drop down
                        var $dropdownList = $(
                            '<ul class="dropdown-menu"></ul>'
                        ).appendTo($addButton);
                        // Add the drop down items
                        for (i = 0; i < buttonDropdownItems.length; i++){
                            $dropdownList.append(buttonDropdownItems[i]);
                        }
                    }

                    var addItem = function(columnConfiguration) {
                        var col;
                        var redraw = false;
                        if (_.isEmpty(that.columns)) {
                            // Only the button has been drawn, so we want to
                            // render again, this time with a table.
                            redraw = true;
                        }
                        col = that.initColumnAsColumn(
                            Column.init(columnConfiguration, that)
                        );
                        that.fire('add-column', col);
                        if (redraw) {
                            that.render();
                        }
                    };
                    $(".add-property-item", $addButton).click(function () {
                        addItem({hasAutocomplete: true});
                    });
                    $(".add-calculation-item", $addButton).click(function () {
                        addItem({hasAutocomplete: false, format: "calculate"});
                    });

                    if (! _.isEmpty(this.columns)) {
                        $table = $('<table class="table table-condensed"/>'
                        ).addClass('detail-screen-table'
                        ).appendTo($box);
                        $thead = $('<thead/>').appendTo($table);

                        $tr = $('<tr/>').appendTo($thead);

                        // grip
                        $('<th/>').addClass('detail-screen-icon').appendTo($tr);

                        $('<th/>').addClass('detail-screen-field').text(DetailScreenConfig.message.FIELD).appendTo($tr);
                        $('<th/>').addClass('detail-screen-header').text(DetailScreenConfig.message.HEADER).appendTo($tr);
                        $('<th/>').addClass('detail-screen-format').text(DetailScreenConfig.message.FORMAT).appendTo($tr);

                        $('<th/>').addClass('detail-screen-icon').appendTo($tr);
                        $columns = $('<tbody/>').addClass('detail-screen-columns').appendTo($table);

                        for (i = 0; i < this.columns.length; i += 1) {
                            this.addColumn(this.columns[i], $columns, i);
                        }

                        this.$columns = $columns;

                        // Add the button
                        $buttonRow = $(
                            '<tr>' +
                                '<td class="detail-screen-icon"></td>' +
                                '<td class="detail-screen-field button-cell">' +
                                '</td>' +
                                '<td class="detail-screen-header"></td>' +
                                '<td class="detail-screen-format"></td>' +
                                '<td class="detail-screen-icon"></td>' +
                            '</tr>'
                        );
                        $('.button-cell', $buttonRow).append($addButton);
                        var $specialTableBody = $('<tbody/>').addClass('detail-screen-columns slim').appendTo($table);
                        $specialTableBody.append($buttonRow);
                        // init UI events
                        this.initUI($columns);
                    } else {
                        $addButton.appendTo($box);
                    }
                }
            },
            initUI: function (rows) {
                var that = this;
                this.$columns.sortable({
                    handle: '.grip',
                    items: ">*:not(:has(.sort-disabled))",
                    update: function (e, ui) {
                        var fromIndex = ui.item.data('index');
                        var toIndex = rows.find('tr').get().indexOf(ui.item[0]);

                        function reorder(list) {
                            var tmp = list.splice(fromIndex, 1)[0];
                            list.splice(toIndex, 0, tmp);
                        }
                        reorder(that.columns);
                        that.fire('change');
                    }
                });
            }
        };
        return Screen;
    }());
    DetailScreenConfig = (function () {
        var DetailScreenConfig = function ($listHome, $detailHome, spec) {
            var that = this;
            this.$listHome = $listHome;
            this.$detailHome = $detailHome;
            this.properties = spec.properties;
            this.screens = [];
            this.model = spec.model || 'case';
            this.sortRows = new SortRows(this.properties, spec.edit);
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
            this.edit = spec.edit;
            this.saveUrl = spec.saveUrl;
            this.calculationEnabled = spec.calculationEnabled;

            var filter_xpath = spec.state.short.filter;
            this.filter = new filterViewModel(filter_xpath ? filter_xpath : null);

            /**
             * Add a Screen to this DetailScreenConfig
             * @param pair
             * @param columnType
             * The type of case properties that this Screen will be displaying,
             * either "short" or "long".
             */
            function addScreen(pair, columnType, $location) {

                var screen = Screen.init(
                    $('<div/>'),
                    pair,
                    that,
                    {
                        lang: that.lang,
                        langs: that.langs,
                        edit: that.edit,
                        properties: that.properties,
                        saveUrl: that.saveUrl,
                        $location: $location,
                        columnKey: columnType,
                        containsSortConfiguration: columnType == "short",
                        containsParentConfiguration: columnType == "short",
                        containsFilterConfiguration: columnType == "short"
                    }
                );
                that.screens.push(screen);
                $location.append(screen.$home);
            }

            if (spec.state.short !== undefined) {
                addScreen(spec.state, "short", this.$listHome);
            }
            if (spec.state.long !== undefined) {
                addScreen(spec.state, "long", this.$detailHome);
            }
        };
        DetailScreenConfig.init = function ($listHome, $detailHome, spec) {
            var ds = new DetailScreenConfig($listHome, $detailHome, spec);
            var type = spec.state.type;
            var $sortRowsHome = $('#' + type + '-detail-screen-sort');
            var $filterHome = $('#' + type + '-filter');
            var $parentSelectHome = $('#' + type + '-detail-screen-parent');
            ko.applyBindings(ds.sortRows, $sortRowsHome.get(0));
            ko.applyBindings(ds.filter, $filterHome.get(0));
            if ($parentSelectHome.get(0) && ds.hasOwnProperty('parentSelect')){
                ko.applyBindings(ds.parentSelect, $parentSelectHome.get(0));
                $parentSelectHome.on('change', '*', function () {
                    ds.screens[0].fire('change');
                });
            }
            return ds;
        };
        return DetailScreenConfig;
    }());

    DetailScreenConfig.message = {
        EMPTY_SCREEN: 'No detail screen configured',

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

    if (window.FEATURE_mm_case_properties) {
        DetailScreenConfig.MENU_OPTIONS.push(
            {value: "picture", label: DetailScreenConfig.message.PICTURE_FORMAT},
            {value: "audio", label: DetailScreenConfig.message.AUDIO_FORMAT}
        );
    }

    if (window.FEATURE_enable_enum_image) {
        DetailScreenConfig.MENU_OPTIONS.push(
            {value: "enum-image", label: DetailScreenConfig.message.ENUM_IMAGE_FORMAT + ' (Preview!)'}
        );
    }

    if (window.FEATURE_enable_calc_xpaths) {
        DetailScreenConfig.MENU_OPTIONS.push(
            {value: "calculate", label: DetailScreenConfig.message.CALC_XPATH_FORMAT + ' (Preview!)'}
        );
    }

    DetailScreenConfig.field_format_warning = $('<span/>').addClass('help-inline')
        .text("Must begin with a letter and contain only letters, numbers, '-', and '_'");

    DetailScreenConfig.field_val_re = new RegExp(
        '^(' + word + ':)*(' + word + '\\/)*#?' + word + '$'
    );

    return DetailScreenConfig;
}());
