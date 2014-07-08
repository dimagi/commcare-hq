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
    }
};

var SortRow = function (field, type, direction) {
    var self = this;
    self.field = ko.observable(field);
    self.type = ko.observable(type);
    self.direction = ko.observable(direction);

    self.type.subscribe(function () {
        window.sortRowSaveButton.fire('change');
    });
    self.direction.subscribe(function () {
        window.sortRowSaveButton.fire('change');
    });

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

var SortRows = function () {
    var self = this;
    self.sortRows = ko.observableArray([]);

    self.addSortRow = function (field, type, direction) {
        self.sortRows.push(new SortRow(field, type, direction));
    };

    self.removeSortRow = function (row) {
        self.sortRows.remove(row);
        window.sortRowSaveButton.fire('change');
    };

    self.rowCount = ko.computed(function () {
        return self.sortRows().length;
    });
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
    var field_val_re = RegExp(
        '^(' + word + ':)*(' + word + '\\/)*#?' + word + '$'
    );
    var field_format_warning = $('<span/>').addClass('help-inline')
        .text("Must begin with a letter and contain only letters, numbers, '-', and '_'");

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
            this.original.header = this.original.header || {};
            this.original.format = this.original.format || "plain";
            this.original['enum'] = this.original['enum'] || [];
            this.original.late_flag = this.original.late_flag || 30;
            this.original.filter_xpath = this.original.filter_xpath || "";
            this.original.calc_xpath = this.original.calc_xpath || ".";
            var icon = (CC_DETAIL_SCREEN.isAttachmentProperty(this.original.field)
                           ? COMMCAREHQ.icons.PAPERCLIP : null);


            this.original.time_ago_interval = this.original.time_ago_interval || DetailScreenConfig.TIME_AGO.year;

            this.screen = screen;
            this.lang = screen.lang;

            this.includeInShort = uiElement.checkbox().val(orDefault(this.original.includeInShort, true));
            this.includeInLong = uiElement.checkbox().val(orDefault(this.original.includeInLong, true));

            this.model = uiElement.select([
                {label: "Case", value: "case"}
            ]).val(this.original.model);
            this.field = uiElement.input().val(this.original.field).setIcon(icon);
            this.format_warning = field_format_warning.clone().hide();

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
                that.header.ui.find('input').addClass('input-small');
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
                'includeInShort',
                'includeInLong',
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

            this.$add = $('<i></i>').addClass(COMMCAREHQ.icons.ADD).click(function () {
                if (that.field.val() && field_val_re.test(that.field.val())) {
                    that.duplicate();
                } else {
                    that.field.$edit_view.focus();
                }
            }).css({cursor: 'pointer'}).attr('title', DetailScreenConfig.message.ADD_COLUMN);
            this.$delete = $('<i></i>').addClass(COMMCAREHQ.icons.DELETE).click(function () {
                $(this).remove();
                that.screen.fire('delete-column', that);
            }).css({cursor: 'pointer'}).attr('title', DetailScreenConfig.message.DELETE_COLUMN);

            this.$sortLink = $('<a href="#">Sort by this</a>').click(function (e) {
                that.screen.config.sortRows.addSortRow(that.field.val(), '', '');
                e.preventDefault();
                e.stopImmediatePropagation();
            });
        }

        Column.init = function (col, screen) {
            return new Column(col, screen);
        };
        Column.prototype = {
            duplicate: function () {
                this.screen.fire('add-column', this);
            },
            serialize: function (keepShortLong) {
                var column = this.original;
//                column.model = this.model.val();
                column.field = this.field.val();
                column.header[this.lang] = this.header.val();
                column.format = this.format.val();
                column['enum'] = this.enum_extra.getItems();
                column.late_flag = parseInt(this.late_flag_extra.val(), 10);
                column.time_ago_interval = parseFloat(this.time_ago_extra.val());
                column.filter_xpath = this.filter_xpath_extra.val();
                column.calc_xpath = this.calc_xpath_extra.val();
                if (!keepShortLong) {
                    delete column.includeInShort;
                    delete column.includeInLong;
                } else {
                    column.includeInShort = this.includeInShort.val();
                    column.includeInLong = this.includeInLong.val();
                }
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
        function Screen($home, spec, config, options) {
            var i, column, model, property, header,
                that = this, columns;
            eventize(this);
            this.type = spec.type;
            this.saveUrl = options.saveUrl;
            this.$home = $home;
            this.config = config;
            this.edit = options.edit;
            this.columns = [];
            this.suggestedColumns = [];
            this.model = config.model;
            this.lang = options.lang;
            this.langs = options.langs || [];
            this.properties = options.properties;

            function fireChange() {
                that.fire('change');
            }
            function initColumnAsColumn(column) {
                column.includeInShort.setEdit(that.edit);
                column.includeInLong.setEdit(that.edit);
                column.model.setEdit(false);
                column.field.setEdit(false);
                column.header.setEdit(that.edit);
                column.format.setEdit(that.edit);
                column.enum_extra.setEdit(that.edit);
                column.late_flag_extra.setEdit(that.edit);
                column.filter_xpath_extra.setEdit(that.edit);
                column.calc_xpath_extra.setEdit(that.edit);
                column.time_ago_extra.setEdit(that.edit);
                column.setGrip(true);
                column.on('change', fireChange);
                return column;
            }

            function initColumnAsSuggestion(column) {
                column.includeInShort.setEdit(false);
                column.includeInLong.setEdit(false);
                column.model.setEdit(false);
                column.field.setEdit(false);
                column.header.setEdit(false);
                column.format.setEdit(false);
                column.enum_extra.setEdit(false);
                column.late_flag_extra.setEdit(false);
                column.filter_xpath_extra.setEdit(false);
                column.calc_xpath_extra.setEdit(false);
                column.time_ago_extra.setEdit(false);
                column.setGrip(false);
                return column;
            }

            var longColumns = spec.long ? spec.long.columns : [];
            columns = lcsMerge(spec.short.columns, longColumns, _.isEqual).merge;

            // set up the columns
            for (i = 0; i < columns.length; i += 1) {
                column = columns[i].token;
                column.includeInShort = columns[i].x;
                column.includeInLong = columns[i].y;

                this.columns[i] = Column.init(column, this);
                initColumnAsColumn(this.columns[i]);
            }

            // set up the custom column
            this.customColumn = Column.init({model: this.model, format: "plain", includeInShort: false}, this);
            this.customColumn.field.on('change', function () {
                that.customColumn.header.val(getPropertyTitle(this.val()));
                if (this.val() && !field_val_re.test(this.val())) {
                    that.customColumn.format_warning.show().parent().addClass('error');
                } else {
                    that.customColumn.format_warning.hide().parent().removeClass('error');
                }
            }).$edit_view.autocomplete({
                source: function (request, response) {
                    var availableTags = _.map(that.properties, function(value) {
                        var label = value;
                        if (CC_DETAIL_SCREEN.isAttachmentProperty(value)) {
                            label = ('<span class="icon-paper-clip"></span> '
                                     + label.substring(label.indexOf(":") + 1));
                        }
                        return {value: value, label: label};
                    });
                    response(
                        $.ui.autocomplete.filter(availableTags,  request.term)
                    );
                },
                minLength: 0,
                delay: 0,
                select: function (event, ui) {
                    that.customColumn.field.val(ui.item.value);
                    that.customColumn.field.fire('change');
                }
            }).focus(function () {
                $(this).val("").trigger('change');
                $(this).autocomplete('search');
            }).data("autocomplete")._renderItem = function (ul, item) {
                return $("<li></li>")
                    .data("item.autocomplete", item)
                    .append($("<a></a>").html(item.label))
                    .appendTo(ul);
            };

            // set up suggestion columns
            var info;
            for (i = 0; i < this.properties.length; i += 1) {
                property = this.properties[i];
                header = {};
                header[this.lang] = getPropertyTitle(property);
                column = Column.init({
                    model: model,
                    field: property,
                    header: header,
                    includeInShort: false
                }, this);
                initColumnAsSuggestion(column);
                this.suggestedColumns.push(column);
            }
            this.suggestedColumns = _(this.suggestedColumns).sortBy(function (column) {
                return [
                    /\//.test(column.field.val()) ? 2 : 1,
                    column.field.val()
                ];
            });

            this.saveButton = COMMCAREHQ.SaveButton.init({
                unsavedMessage: DetailScreenConfig.message.UNSAVED_MESSAGE,
                save: function () {
                    that.save();
                }
            });
            window.sortRowSaveButton = this.saveButton;

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
                initColumnAsColumn(column);
                if (i !== -1) {
                    this.columns.splice(i + 1, 0, column);
                } else {
                    this.columns.push(column);
                }
                $tr = this.addColumn(column, this.$columns, this.$columns.length, false);
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
                var parentSelect;
                if (this.config.hasOwnProperty('parentSelect')) {
                    parentSelect = JSON.stringify({
                        module_id: this.config.parentSelect.moduleId(),
                        relationship: 'parent',
                        active: this.config.parentSelect.active()
                    });
                }
                this.saveButton.ajax({
                    url: this.saveUrl,
                    type: "POST",
                    data: {
                        type: this.type,
                        screens: JSON.stringify(this.serialize()),
                        parent_select: parentSelect
                    },
                    dataType: 'json',
                    success: function (data) {
                        COMMCAREHQ.app_manager.updateDOM(data.update);
                    }
                });
            },
            serialize: function () {
                var i, column,
                    shortColumns = [],
                    longColumns = [];
                for (i = 0; i < this.columns.length; i += 1) {
                    column = this.columns[i];
                    if (column.includeInShort.val()) {
                        shortColumns.push(column.serialize());
                    }
                    if (column.includeInLong.val()) {
                        longColumns.push(column.serialize());
                    }
                }
                return {
                    short: shortColumns,
                    long: longColumns,
                    sort_elements: ko.toJS(this.config.sortRows.sortRows)
                };
            },
            addColumn: function (column, $tbody, i, suggested) {
                var $tr = $('<tr/>').data('index', i).appendTo($tbody);
                if (suggested && i !== -1) {
                    $tr.addClass('detail-screen-suggestion').attr('title', DetailScreenConfig.message.ADD_COLUMN);
                }
                if (this.edit) {
                    $('<td/>').addClass('detail-screen-icon').append(column.$grip).appendTo($tr);
                } else {
                    $('<td/>').addClass('detail-screen-icon').appendTo($tr);
                }

                $('<td/>').addClass('detail-screen-checkbox').append(column.includeInShort.ui).appendTo($tr);
                $('<td/>').addClass('detail-screen-checkbox').append(column.includeInLong.ui).appendTo($tr);

                if (!column.field.edit) {
                    column.field.setHtml(CC_DETAIL_SCREEN.getFieldHtml(column.field.val()));
                }
                var dsf = $('<td/>').addClass('detail-screen-field control-group').append(column.field.ui);
                dsf.append(column.format_warning);
                if (column.field.value && !field_val_re.test(column.field.value)) {
                    column.format_warning.show().parent().addClass('error');
                }
                dsf.appendTo($tr);

                $('<td/>').addClass('detail-screen-header').append(column.header.ui).appendTo($tr);
                $('<td/>').addClass('detail-screen-format').append(column.format.ui).appendTo($tr);
                column.format.fire('change');

                var sortLine = $('<td/>').addClass('detail-screen-extra');
                // Only add sort link if we are using new sort feature and
                // this is not the blank field row
                if (window.enableNewSort && column.field.value) {
                    sortLine.append(column.$sortLink)
                }
                sortLine.appendTo($tr);

                if (this.edit) {
                    $('<td/>').addClass('detail-screen-icon').append(
                        suggested ? column.$add : column.$copy
                    ).appendTo($tr);
                    $('<td/>').addClass('detail-screen-icon').append(
                        suggested ? "" : column.$delete
                    ).appendTo($tr);
                } else {
                    $('<td/>').addClass('detail-screen-icon').appendTo($tr);
                    $('<td/>').addClass('detail-screen-icon').appendTo($tr);
                }
                return $tr;
            },
            render: function () {
                var $table, $columns, $suggestedColumns, $thead, $tr, i, $box;
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
                            var $detailBody = $('#' + this.type + '-detail-screen-config-body');
                            $('<div id="saveBtn" class="clearfix">')
                                .append(this.saveButton.ui)
                                .prependTo($detailBody);
                        } else {
                            $('<div class="clearfix">')
                                .append(this.saveButton.ui)
                                .prependTo($box);
                        }
                    }
                    $table = $('<table class="table table-condensed"/>'
                        ).addClass('detail-screen-table'
                    ).appendTo($box);
                    $thead = $('<thead/>').appendTo($table);

                    $tr = $('<tr/>').appendTo($thead);

                    // grip
                    $('<th/>').addClass('detail-screen-icon').appendTo($tr);

                    $('<th/>').addClass('detail-screen-checkbox').text(DetailScreenConfig.message.SHORT).appendTo($tr).popover(DetailScreenConfig.message.SHORT_POPOVER);
                    $('<th/>').addClass('detail-screen-checkbox').text(DetailScreenConfig.message.LONG).appendTo($tr).popover(DetailScreenConfig.message.LONG_POPOVER);
                    $('<th/>').addClass('detail-screen-field').text(DetailScreenConfig.message.FIELD).appendTo($tr);
                    $('<th/>').addClass('detail-screen-header').text(DetailScreenConfig.message.HEADER).appendTo($tr);
                    $('<th/>').addClass('detail-screen-format').text(DetailScreenConfig.message.FORMAT).appendTo($tr);
                    $('<th/>').addClass('detail-screen-extra').appendTo($tr);

                    $('<th/>').addClass('detail-screen-icon').appendTo($tr);
                    $('<th/>').addClass('detail-screen-icon').appendTo($tr);

                    $columns = $('<tbody/>').addClass('detail-screen-columns').appendTo($table);
                    $suggestedColumns = $('<tbody/>').appendTo($table);

                    for (i = 0; i < this.columns.length; i += 1) {
                        this.addColumn(this.columns[i], $columns, i, false);
                    }

                    if (this.edit) {
                        this.addColumn(this.customColumn, $suggestedColumns, -1, true);

                        for (i = 0; i < this.suggestedColumns.length; i += 1) {
                            this.addColumn(this.suggestedColumns[i], $suggestedColumns, i, true).click(
                                getDuplicateCallback(this.suggestedColumns[i])
                            );
                            this.suggestedColumns[i].includeInShort.ui.hide();
                            this.suggestedColumns[i].includeInLong.ui.hide();
                            this.suggestedColumns[i].$add.hide();
                        }
                    }
                    this.$columns = $columns;

                    // init UI events
                    this.initUI($columns);
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
        var DetailScreenConfig = function ($home, spec) {
            var that = this;
            this.$home = $home;
            this.properties = spec.properties;
            this.screens = [];
            this.model = spec.model || 'case';
            this.sortRows = new SortRows();
            this.lang = spec.lang;
            this.langs = spec.langs || [];
            if (spec.hasOwnProperty('parentSelect')) {
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

            function addScreen(pair) {
                var screen = Screen.init(
                    $('<div/>'),
                    pair,
                    that,
                    {
                        lang: that.lang,
                        langs: that.langs,
                        edit: that.edit,
                        properties: that.properties,
                        saveUrl: that.saveUrl
                    }
                );
                that.screens.push(screen);
                that.$home.append(screen.$home);
            }

            addScreen(spec.state);
        };
        DetailScreenConfig.init = function ($home, spec) {
            var ds = new DetailScreenConfig($home, spec);
            var type = spec.state.type;
            var $sortRowsHome = $('#' + type + '-detail-screen-sort');
            var $parentSelectHome = $('#' + type + '-detail-screen-parent');
            ko.applyBindings(ds.sortRows, $sortRowsHome.get(0));
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

        SHORT: 'List',
        SHORT_POPOVER: {
            title: 'List View',
            content: (
                "Checked properties will be displayed in the case list, where each case is listed as a row on the phone's screen. " +
                "We recommend using 2-3 case properties that will help the mobile worker identify each case."
            ),
            placement: 'top'
        },
        LONG: 'Detail',
        LONG_POPOVER: {
            title: 'Detail View',
            content: (
                "Checked properties will be shown in the detail view that appears after selecting an item in the list view. " +
                "We recommend that you include all properties that the mobile worker will find relevant. "
            ),
            placement: 'top'
        },

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
        FILTER_XPATH_FORMAT: 'Filter (Advanced)',
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
        {value: "filter", label: DetailScreenConfig.message.FILTER_XPATH_FORMAT},
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
    return DetailScreenConfig;
}());
