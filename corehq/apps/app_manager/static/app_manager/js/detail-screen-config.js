var DetailScreenConfig = (function () {
    "use strict";
    var DetailScreenConfig, Screen, Column;
    Column = (function () {
        function Column(col, screen) {
            this.screen = screen;
            this.model = col.model;
            this.field = col.field;
            this.lang = screen.lang;
            
            this.setHeader(col.header ? col.header[this.lang] : "");
            this.setSelected(col.selected);
            this.setEnum((col['enum'] || {})[this.lang]);
            this.setFormat(col.format);
            console.log(col);
        }
        Column.init = function (col, screen) {
            return new Column(col, screen);
        };
        Column.prototype = {
            setHeader: function (header) {
                this.header = header;
                this.$header = (this.$header || $('<input type="text"/>')).val(header);
            },
            setSelected: function (selected) {
                var gripClass = "ui-icon-grip-dotted-horizontal";
                if (this.selected !== selected) {
                    this.selected = selected;
                    this.$selected = (this.$selected || $('<input type="checkbox"/>')).prop("checked", selected);
                    if (selected) {
                        this.$grip = $('<div class="grip ui-icon"/>').addClass(gripClass);
                    } else {
                        this.$grip = $('<span class="sort-disabled"></span>');
                    }
                }
            },
            setFormat: function (format) {
                if (!this.hasOwnProperty('$format')) {
                    var i, option, options = [
                        {"label": "Plain", "value": "plain"},
                        {"label": "Date", "value": "date"},
                        {"label": "Years Ago", "value": "years-ago"},
                        {"label": "Phone Number", "value": "phone"},
                        {"label": "Enum", "value": "enum"},
                        {"label": "Late Flag", "value": "late-flag"},
                    ];
                    this.$format = $('<select/>');
                    for (i = 0; i < options.length; i += 1) {
                        option = options[i];
                        $('<option/>').text(option.label).val(option.value).appendTo(this.$format);
                    }
                }
                this.format = format;
                this.$format.val(format);
                if (format === "enum") {
                    this.$extra = this.$enum;
                } else {
                    this.$extra = $("<span/>");
                }
            },
            setEnum: function (_enum) {
                this.$enum = (this.$enum || $('<input type="text"/>')).val(_enum);
                this['enum'] = _enum;
            },
            handleSelectedChange: function (e) {
                var selected = this.$selected.prop("checked");
                console.log(selected);
                if (this.selected !== selected) {
                    if (this.selected) {
                        this.screen.columns.splice(this.screen.columns.indexOf(this), 1);
                        this.screen.unselectedColumns.push(this);
                    } else {
                        this.screen.unselectedColumns.splice(this.screen.unselectedColumns.indexOf(this), 1);
                        this.screen.columns.push(this);
                    }
                    this.setSelected(selected);
                    this.screen.render();
                }
            },
            handleFormatChange: function (e) {
                var format = this.$format.val();
                this.setFormat(format);
                this.screen.render();
            },
            initUI: function () {
                var that = this;
                this.initSelected();
                this.$format.change(function (e) {
                    that.handleFormatChange(e);
                });
                this.$enum.change(function (e) {
                    that.setEnum(that.$enum.val());
                });
            },
            initSelected: function () {
                var that = this;
                this.$selected.change(function (e) {
                    that.handleSelectedChange(e);
                });
            }
        };
        return Column;
    }());
    Screen = (function () {
        var sectionLabels = {
            case_short: "Case List View",
            case_long: "Case Full View",
            ref_short: "Referral List View",
            ref_long: "Referral Full View"
        };
        function Screen($home, spec, options) {
            var i, column, model, property,
                selectedProperties = {"case": {}, referral: {}};
            this.$home = $home;
            this.columns = [];
            this.unselectedColumns = [];
            this.type = spec.type;
            this.model = this.type === "ref_short" || this.type === "ref_long" ? "referral" : "case";
            this.lang = options.lang;
            this.properties = options.properties;

            for (i = 0; i < spec.columns.length; i += 1) {
                column = spec.columns[i];
                column.selected = true;
                this.columns[i] = Column.init(column, this);
                selectedProperties[column.model][column.field] = true;
            }
            for (model in this.properties) {
                if (selectedProperties.hasOwnProperty(model) && !(this.model === 'case' && model === 'referral')) {
                    for (i = 0; i < this.properties[model].length; i += 1) {
                        property = this.properties[model][i];
                        if (!selectedProperties[model].hasOwnProperty(property)) {
                            this.unselectedColumns.push(Column.init({
                                model: model,
                                field: property,
                                selected: false
                            }, this));
                        }
                    }
                }
            }
            this.render();
        }
        Screen.init = function ($home, spec, lang) {
            return new Screen($home, spec, lang);
        };
        Screen.prototype = {
            render: function () {
                var $table, $columns, $unselectedColumns, $tr, i, showColumn,
                    that = this,
                    rows = [];
                this.$home.html("");
                $("<h1/>").text(sectionLabels[this.type]).appendTo(this.$home);
                
                $table = $("<table/>").appendTo(this.$home);

                $tr = $("<tr/>").appendTo($table);

                $("<th/>").appendTo($tr);
                $("<th/>").appendTo($tr);
                if (this.model === "referral") {
                    $("<th/>").text("Model").appendTo($tr);
                }
                $("<th/>").text("Property").appendTo($tr);
                $("<th/>").text("Header").appendTo($tr);
                $("<th/>").text("Format").appendTo($tr);
                $("<th/>").appendTo($tr); // Extra

                $columns = $("<tbody/>").appendTo($table);
                $unselectedColumns = $("<tbody/>").appendTo($table);

                this.unselectedColumns.sortBy(function () {
                    return [this.model, this.field];
                });

                showColumn = function (column, $tbody, i) {
                    $tr = $("<tr/>").data('index', i).appendTo($tbody);

                    $("<td/>").append(column.$grip).appendTo($tr);
                    $("<td/>").append(column.$selected).appendTo($tr);
                    if (that.model === 'referral') {
                        $("<td/>").text(column.model).appendTo($tr);
                    }
                    $("<td/>").html("<code>" + column.field + "</code>").appendTo($tr);
                    $("<td/>").append(column.$header).appendTo($tr);
                    $("<td/>").append(column.$format).appendTo($tr);
                    $("<td/>").append(column.$extra).appendTo($tr);
                    rows.push($tr.elem);
                };
                for (i = 0; i < this.columns.length; i += 1) {
                    showColumn(this.columns[i], $columns, i);
                }
                for (i = 0; i < this.unselectedColumns.length; i += 1) {
                    showColumn(this.unselectedColumns[i], $unselectedColumns, i);
                }
                this.$columns = $columns;

                // init UI events
                this.initUI(rows);
            },
            initUI: function (rows) {
                var i, column,
                    that = this;
                this.$columns.sortable({
                    handle: '.grip',
                    items: ">*:not(:has(.sort-disabled))",
                    update: function (e, ui) {
                        var fromIndex = ui.item.data('index'),
                            // rows is a closure variable
                            toIndex = rows.indexOf(ui.item);

                        function reorder(list) {
                            var tmp = list.splice(fromIndex, 1)[0];
                            list.splice(toIndex, 0, tmp);
                        }
                        reorder(rows);
                        reorder(that.columns);
                    }
                });
                for (i = 0; i < this.columns.length; i += 1) {
                    column = this.columns[i];
                    column.initUI();
                }
                for (i = 0; i < this.unselectedColumns.length; i += 1) {
                    column = this.unselectedColumns[i];
                    column.initUI();
                }
            }
        };
        return Screen;
    }());
    DetailScreenConfig = (function () {
        var DetailScreenConfig = function ($home, spec) {
            var detail_type;
            this.$home = $home;
            this.properties = spec.properties;
            this.state = {};
            this.lang = spec.lang;
            for (detail_type in spec.state) {
                if (spec.state.hasOwnProperty(detail_type)) {
                    this.state[detail_type] = Screen.init($("<div/>"), spec.state[detail_type], {
                        lang: this.lang,
                        properties: this.properties
                    });
                    this.$home.append(this.state[detail_type].$home);
                }
            }
        };

        DetailScreenConfig.init = function ($home, spec) {
            return new DetailScreenConfig($home, spec);
        };
        return DetailScreenConfig;
    }());
    return DetailScreenConfig;
}());