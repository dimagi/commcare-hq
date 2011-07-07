var DetailScreenConfig = (function () {
    "use strict";
    var DetailScreenConfig, Screen, Column;
    Column = (function () {
        function Column(col, lang) {
            this.model = col.model;
            this.field = col.field;
            this.lang = lang;
            this.setHeader(col.header ? col.header[this.lang] : "");
            this.setSelected(col.selected);
        }
        Column.init = function (col, lang) {
            return new Column(col, lang);
        };
        Column.prototype = {
            setHeader: function (header) {
                this.header = header;
                this.$header = (this.$header || $('<input type="text"/>')).val(header);
            },
            setSelected: function (selected) {
                var gripClass = "ui-icon-grip-dotted-horizontal";
                this.selected = selected;
                this.$selected = (this.$selected || $('<input type="checkbox"/>')).prop("checked", selected);
                if (selected) {
                    this.$grip = $('<div class="grip ui-icon"/>').addClass(gripClass);
                } else {
                    this.$grip = $('<span class="sort-disabled"></span>');
                }
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
            var i,
                selectedProperties = {"case": {}, referral: {}},
                column, model, property;
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
                this.columns[i] = Column.init(column, this.lang);
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
                            }));
                        }
                    }
                }
            }
            this.render();
            this.$columns.sortable({
                handle: '.grip',
                items: ">*:not(:has(.sort-disabled))"
            });
        }
        Screen.init = function ($home, spec, lang) {
            return new Screen($home, spec, lang);
        };
        Screen.prototype = {
            render: function () {
                var $table, $columns, $unselectedColumns, $tr, i, column, showColumn,
                    that = this;
                $("<h1/>").text(sectionLabels[this.type]).appendTo(this.$home);
                
                $table = $("<table/>").appendTo(this.$home);

                $tr = $("<tr/>").appendTo($table);

                $("<th/>").appendTo($tr);
                $("<th/>").text("Selected").appendTo($tr);
                if (this.model === "referral") {
                    $("<th/>").text("Model").appendTo($tr);
                }
                $("<th/>").text("Property").appendTo($tr);
                $("<th/>").text("Header").appendTo($tr);

                $columns = $("<tbody/>").appendTo($table);
                $unselectedColumns = $("<tbody/>").appendTo($table);

                showColumn = function (column, $tbody) {
                    $tr = $("<tr/>").appendTo($tbody);

                    $("<td/>").append(column.$grip).appendTo($tr);
                    $("<td/>").append(column.$selected).appendTo($tr);
                    if (that.model === 'referral') {
                        $("<td/>").text(column.model).appendTo($tr);
                    }
                    $("<td/>").text(column.field).appendTo($tr);
                    $("<td/>").append(column.$header).appendTo($tr);
                };
                for (i = 0; i < this.columns.length; i += 1) {
                    showColumn(this.columns[i], $columns);
                }
                for (i = 0; i < this.unselectedColumns.length; i += 1) {
                    showColumn(this.unselectedColumns[i], $unselectedColumns);
                }
                this.$columns = $columns;
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