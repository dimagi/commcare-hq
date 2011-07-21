/*globals $, uiElement, eventize */

var DetailScreenConfig = (function () {
    "use strict";
    var DetailScreenConfig, Screen, Column;
    Column = (function () {
        function Column(col, screen) {
            /*
                column properites: model, field, header, format
                column extras: enum
            */
            var that = this;
            this.original = col;

            this.original.model = this.original.model || "case";
            this.original.field = this.original.field || "";
            this.original.header = this.original.header || {};
            this.original.format = this.original.format || "plain";

            this.screen = screen;
            this.lang = screen.lang;

            this.includeInShort = uiElement.checkbox().val(col.includeInShort || false);
            this.includeInLong = uiElement.checkbox().val(col.includeInLong || false);

            this.model = uiElement.select([
                {label: "Case", value: "case"},
                {label: "Referral", value: "referral"}
            ]).val(col.model);
            this.field = uiElement.input().val(col.field);
            this.header = uiElement.input().val(col.header ? col.header[this.lang] || "" : "");
            this.format = uiElement.select([
                {"label": "Plain", "value": "plain"},
                {"label": "Date", "value": "date"},
                {"label": "Years Ago", "value": "years-ago"},
                {"label": "Phone Number", "value": "phone"},
                {"label": "Enum", "value": "enum"},
                {"label": "Late Flag", "value": "late-flag"}
            ]).val(col.format || null);

            this.enum_extra = uiElement.input().val((col['enum'] || {})[this.lang] || "");

            this.$extra = $('<span/>');
            //this.setFormat(col.format);

            this.format.on('change', function () {
                that.$extra.find('> *').detach();
                if (this.val() === "enum") {
                    that.$extra.append(that.enum_extra.ui);
                }
            }).fire('change');

            this.$add = $('<div class="ui-icon"/>').addClass(Column.ADD).click(function () {
                that.screen.fire('add-column', that);
            }).css({cursor: 'pointer'});
            this.$delete = $('<div class="ui-icon"/>').addClass(Column.DELETE).click(function () {
                that.screen.fire('delete-column', that);
            }).css({cursor: 'pointer'});
        }
        Column.GRIP = "ui-icon-grip-dotted-horizontal";
        Column.ADD = "ui-icon-plusthick";
        Column.DELETE = "ui-icon-closethick";

        Column.init = function (col, screen) {
            return new Column(col, screen);
        };
        Column.prototype = {
            serialize: function () {
                var column = this.original;
                column.model = this.model.val();
                column.field = this.field.val();
                column.header[this.lang] = this.header.val();
                column.format = this.format.val();
                column['enum'] = this.enum_extra.val();
                delete column.includeInShort;
                delete column.includeInLong;
                return column;
            },
            setGrip: function (grip) {
                if (this.grip !== grip) {
                    this.grip = grip;
                    if (grip) {
                        this.$grip = $('<div class="grip ui-icon"/>').addClass(Column.GRIP).css({
                            cursor: 'move'
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
        var sectionLabels = {
            'case': "Case Details",
            referral: "Referral Details"
        };
        function Screen($home, spec, options) {
            var i, column, model, property, header,
                that = this, columns;
            eventize(this);
            this.$home = $home;
            this.edit = options.edit;
            this.columns = [];
            this.suggestedColumns = [];
            this.model = spec.short.type === "ref_short" ? "referral" : "case";
            this.lang = options.lang;
            this.properties = options.properties;

            function initColumnAsColumn(column) {
                column.includeInShort.setEdit(that.edit);
                column.includeInLong.setEdit(that.edit);
                column.model.setEdit(false);
                column.field.setEdit(false);
                column.header.setEdit(that.edit);
                column.format.setEdit(that.edit);
                column.enum_extra.setEdit(that.edit);
                column.setGrip(true);
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
                column.setGrip(false);
                return column;
            }

            columns = lcsMerge(spec.short.columns, spec.long.columns, _.isEqual).merge;

            for (i = 0; i < columns.length; i += 1) {
                column = columns[i].token;
                column.includeInShort = columns[i].x;
                column.includeInLong = columns[i].y;
                this.columns[i] = Column.init(column, this);
                initColumnAsColumn(this.columns[i]);
            }

            this.customColumn = Column.init({model: "case", format: "plain"}, this);

            function toTitleCase(str) {
                return str.replace('_', ' ').replace('-', ' ').replace(/\w\S*/g, function (txt) {
                    return txt.charAt(0).toUpperCase() + txt.substr(1).toLowerCase();
                });
            }

            for (model in this.properties) {
                if (this.properties.hasOwnProperty(model) && !(this.model === 'case' && model === 'referral')) {
                    for (i = 0; i < this.properties[model].length; i += 1) {
                        property = this.properties[model][i];
                        header = {};
                        header[this.lang] = toTitleCase(property);
                        column = Column.init({
                            model: model,
                            field: property,
                            header: header
                        }, this);
                        initColumnAsSuggestion(column);
                        this.suggestedColumns.push(column);
                    }
                }
            }

            this.saveButton = {
                ui: $('<span/>').text('Save').click(function () {
                    console.log(JSON.stringify(that.serialize()));
                })
            };

            this.render();
//            this.$home.find('*').change(function () {
//                console.log(JSON.stringify(that.serialize()));
//            });
            this.on('add-column', function (column) {
                column = column.serialize();
                column = Column.init(column, this);
                initColumnAsColumn(column);
                this.columns.push(column);
                this.addColumn(column, this.$columns, this.$columns.length, false).hide().fadeIn();
            });
            this.on('delete-column', function (column) {
                var i = this.columns.indexOf(column);
                this.$columns.find('tr:nth-child(' + (i + 1).toString() + ')').fadeOut(function () {
                    $(this).remove();
                });
                this.columns.splice(i, 1);
            });
        }
        Screen.init = function ($home, spec, lang) {
            return new Screen($home, spec, lang);
        };
        Screen.prototype = {
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
                if (this.model == 'case') {
                    return {
                        'case_short': shortColumns,
                        'case_long': longColumns
                    };
                } else {
                    return {
                        'ref_short': shortColumns,
                        'ref_long': longColumns
                    };
                }
            },
            addColumn: function (column, $tbody, i, suggested) {
                var $tr = $("<tr/>").data('index', i).appendTo($tbody);
                if (suggested) {
                    $tr.addClass('detail-screen-suggestion');
                }
                if (this.edit) {
                    $("<td/>").addClass('detail-screen-icon').append(column.$grip).appendTo($tr);
                    $("<td/>").addClass('detail-screen-icon').append(
                        suggested ? column.$add : column.$delete
                    ).appendTo($tr);
                } else {
                    $("<td/>").addClass('detail-screen-icon').appendTo($tr);
                    $("<td/>").addClass('detail-screen-icon').appendTo($tr);
                }
                
                $('<td/>').append(column.includeInShort.ui).appendTo($tr);
                $('<td/>').append(column.includeInLong.ui).appendTo($tr);

                if (this.model === 'referral') {
                    $("<td/>").addClass('detail-screen-model').append(column.model.ui).appendTo($tr);
                } else {
                    $('<td/>').addClass('detail-screen-model').appendTo($tr);
                }
                $("<td/>").addClass('detail-screen-field').append(column.field.ui.addClass('code')).appendTo($tr);
                $("<td/>").addClass('detail-screen-header').append(column.header.ui).appendTo($tr);
                $("<td/>").addClass('detail-screen-format').append(column.format.ui).appendTo($tr);
                $("<td/>").addClass('detail-screen-extra').append(column.$extra).appendTo($tr);
                return $tr;
            },
            render: function () {
                var $table, $columns, $suggestedColumns, $tr, i,
                    that = this,
                    rows = [];
                //this.$home.empty();
                $("<h1/>").text(sectionLabels[this.model]).appendTo(this.$home);
                $('<div/>').append(this.saveButton.ui).appendTo(this.$home);
                
                $table = $("<table/>").addClass('detail-screen-table').appendTo(this.$home);
                
                $tr = $("<tr/>").appendTo($table);

//                $("<th/>").appendTo($tr);
                // add or delete
                $("<th/>").addClass('detail-screen-icon').appendTo($tr);
                // grip
                $("<th/>").addClass('detail-screen-icon').appendTo($tr);
                
                $("<th/>").text("Short").appendTo($tr);
                $("<th/>").text("Long").appendTo($tr);
                if (this.model === "referral") {
                    $("<th/>").text("Model").addClass('detail-screen-model').appendTo($tr);
                } else {
                    $('<th/>').addClass('detail-screen-model').appendTo($tr);
                }
                $("<th/>").addClass('detail-screen-field').text("Property").appendTo($tr);
                $("<th/>").addClass('detail-screen-header').text("Label").appendTo($tr);
                $("<th/>").addClass('detail-screen-format').text("Format").appendTo($tr);
                $("<th/>").addClass('detail-screen-extra').appendTo($tr);

                $columns = $("<tbody/>").addClass('detail-screen-columns').appendTo($table);
                $suggestedColumns = $("<tbody/>").appendTo($table);

                this.suggestedColumns.sortBy(function () {
                    return [this.model, this.field];
                });

                for (i = 0; i < this.columns.length; i += 1) {
                    this.addColumn(this.columns[i], $columns, i, false);
                }
                if (this.edit) {
                    this.addColumn(this.customColumn, $suggestedColumns, -1, true);
                    for (i = 0; i < this.suggestedColumns.length; i += 1) {
                        this.addColumn(this.suggestedColumns[i], $suggestedColumns, i, true);
                        this.suggestedColumns[i].includeInShort.ui.hide();
                        this.suggestedColumns[i].includeInLong.ui.hide();
                    }
                }
                this.$columns = $columns;

                // init UI events
                this.initUI($columns);
            },
            initUI: function (rows) {
                var i, column,
                    that = this;
                this.$columns.sortable({
                    handle: '.grip',
                    items: ">*:not(:has(.sort-disabled))",
                    update: function (e, ui) {
                        var fromIndex = ui.item.data('index'),
                            toIndex = rows.find('tr').get().indexOf(ui.item[0]);
                        function reorder(list) {
                            var tmp = list.splice(fromIndex, 1)[0];
                            list.splice(toIndex, 0, tmp);
                        }
                        reorder(that.columns);
                        rows.find('tr').each(function (i) {
                            $(this).data('index', i);
                        });
//                        for (var i = 0; i < that.columns.length; i += 1) {
//                            console.log(that.columns[i].field.val());
//                        }
                    }
                });
            }
        };
        return Screen;
    }());
    DetailScreenConfig = (function () {
        var DetailScreenConfig = function ($home, spec) {
            var detail_type,
                that = this;
            this.$home = $home;
            this.properties = spec.properties;
            this.state = {};
            this.lang = spec.lang;
            this.edit = spec.edit;

            function addScreen(short, long) {
                that.state[detail_type] = Screen.init($('<div/>'), {'short': short, 'long': long}, {
                    lang: that.lang,
                    edit: that.edit,
                    properties: that.properties
                });
                that.$home.append(that.state[detail_type].$home);
            }

            addScreen(spec.state.case_short, spec.state.case_long);
            addScreen(spec.state.ref_short, spec.state.ref_long);
        };

        DetailScreenConfig.init = function ($home, spec) {
            return new DetailScreenConfig($home, spec);
        };
        return DetailScreenConfig;
    }());
    return DetailScreenConfig;
}());