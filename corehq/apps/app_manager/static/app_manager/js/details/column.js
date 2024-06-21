/**
 * Model for a column in the Display Properties section of case list/detail.
 *
 * Initialize with a col and a screen:
 *  - col is the configuration of the column itself, basically a JSON version of
 *    the python DetailColumn model.
 *  - screen is a js model of the table that contains the column.
 *
 * On case detail screens, tabs are implemented as columns with a different
 * set of properties that match python's DetailTab model. The screen model
 * is responsible for creating the tab "columns" and injecting them into itself.
 */
hqDefine("app_manager/js/details/column", function () {
    const uiElement = hqImport('hqwebapp/js/bootstrap3/ui-element');
    const initialPageData = hqImport('hqwebapp/js/initial_page_data').get;
    const microCaseImageName = 'cc_case_image';

    return function (col, screen) {
        /*
            column properties: model, field, header, format
            column extras: enum, late_flag
        */
        const self = {};
        hqImport("hqwebapp/js/bootstrap3/main").eventize(self);
        self.original = JSON.parse(JSON.stringify(col));

        // Set defaults for normal (non-tab) column attributes
        const Utils = hqImport('app_manager/js/details/utils');
        const defaults = {
            calc_xpath: ".",
            enum: [],
            field: "",
            filter_xpath: "",
            format: "plain",
            graph_configuration: {},
            hasAutocomplete: false,
            header: {},
            model: screen.model,
            date_format: "",
            time_ago_interval: Utils.TIME_AGO.year,
            horizontal_align: "left",
            vertical_align: "start",
            font_size: "medium",
            show_border: false,
            show_shading: false,
        };
        _.each(_.keys(defaults), function (key) {
            self.original[key] = self.original[key] || defaults[key];
        });
        self.original.late_flag = _.isNumber(self.original.late_flag) ? self.original.late_flag : 30;

        // Set up tab defaults
        const tabDefaults = {
            isTab: false,
            hasNodeset: false,
            nodeset: "",
            nodesetCaseType: "",
            nodesetFilter: "",
            relevant: "",
        };
        self.original = _.defaults(self.original, tabDefaults);
        let screenHasChildCaseTypes = screen.childCaseTypes && screen.childCaseTypes.length;
        if (!self.original.nodeset && !self.original.nodesetCaseType && screenHasChildCaseTypes) {
            // If there's no nodeset but there are child case types, default to showing a case type
            self.original.nodesetCaseType = screen.childCaseTypes[0];
        }
        _.extend(self, _.pick(self.original, _.keys(tabDefaults)));

        self.original.case_tile_field = ko.utils.unwrapObservable(self.original.case_tile_field) || "";
        self.case_tile_field = ko.observable(self.original.case_tile_field);

        self.coordinatesVisible = ko.observable(true);
        self.tileRowMax = ko.observable(7); // set dynamically by screen
        self.tileColumnMax = ko.observable(13);
        self.tileRowStart = ko.observable(self.original.grid_y + 1 || 1); // converts from 0 to 1-based for UI
        self.tileRowOptions = ko.computed(function () {
            return _.range(1, self.tileRowMax());
        });
        self.tileColumnStart = ko.observable(self.original.grid_x + 1 || 1); // converts from 0 to 1-based for UI
        self.tileColumnOptions = _.range(1, self.tileColumnMax());
        self.tileWidth = ko.observable(self.original.width || self.tileRowMax() - 1);
        self.tileWidthOptions = ko.computed(function () {
            return _.range(1, self.tileColumnMax() + 1 - (self.tileColumnStart() || 1));
        });
        self.tileHeight = ko.observable(self.original.height || 1);
        self.tileHeightOptions = ko.computed(function () {
            return _.range(1, self.tileRowMax() + 1 - (self.tileRowStart() || 1));
        });
        self.horizontalAlign = ko.observable(self.original.horizontal_align || 'left');
        self.horizontalAlignOptions = ['left', 'center', 'right'];

        self.verticalAlign = ko.observable(self.original.vertical_align || 'start');
        self.verticalAlignOptions = ['start', 'center', 'end'];

        self.fontSize = ko.observable(self.original.font_size || 'medium');
        self.fontSizeOptions = ['small', 'medium', 'large'];

        self.showBorder = ko.observable(self.original.show_border || false);
        self.showShading = ko.observable(self.original.show_shading || false);

        self.openStyleModal = function () {
            const $modalDiv = $(document.createElement("div"));
            $modalDiv.attr("data-bind", "template: 'style_configuration_modal'");
            $modalDiv.koApplyBindings(self);
            const $modal = $modalDiv.find('.modal');
            $modal.appendTo('body');
            $modal.modal('show');
            $modal.on('hidden.bs.modal', function () {
                $modal.remove();
            });
        };

        self.tileRowEnd = ko.computed(function () {
            return Number(self.tileRowStart()) + Number(self.tileHeight());
        });
        self.tileColumnEnd = ko.computed(function () {
            return Number(self.tileColumnStart()) + Number(self.tileWidth());
        });
        self.showInTilePreview = ko.computed(function () {
            return !self.isTab && self.coordinatesVisible() && self.tileRowStart() && self.tileColumnStart() && self.tileWidth() && self.tileHeight();
        });
        self.tileContent = ko.observable();
        self.setTileContent = function () {
            self.tileContent(self.header.val());
        };

        self.screen = screen;
        self.lang = screen.lang;
        self.model = uiElement.select([{
            label: "Case",
            value: "case",
        }]).val(self.original.model);

        const icon = Utils.isAttachmentProperty(self.original.field) ? 'fa fa-paperclip' : null;
        self.field = undefined;
        if (self.original.hasAutocomplete) {
            self.field = uiElement.select();
        } else {
            self.field = uiElement.input(self.original.field);
        }
        self.field.setIcon(icon);

        // Make it possible to observe changes to self.field
        // note self observableVal is read only!
        // Writing to it will not update the value of the self.field text input
        self.field.observableVal = ko.observable(self.field.val());
        self.field.on("change", function () {
            self.field.observableVal(self.field.val());
        });

        (function () {
            let i,
                lang,
                visibleVal = "",
                invisibleVal = "";
            if (self.original.header && self.original.header[self.lang]) {
                visibleVal = invisibleVal = self.original.header[self.lang];
            } else {
                for (i = 0; i < self.screen.langs.length; i += 1) {
                    lang = self.screen.langs[i];
                    if (self.original.header[lang]) {
                        visibleVal = self.original.header[lang] +
                            hqImport('hqwebapp/js/ui_elements/ui-element-langcode-button').LANG_DELIN +
                            lang;
                        break;
                    }
                }
            }
            self.header = uiElement.input().val(invisibleVal);
            self.header.setVisibleValue(visibleVal);

            self.nodeset_extra = hqImport("app_manager/js/details/detail_tab_nodeset")(_.extend({
                caseTypes: self.screen.childCaseTypes,
            }, _.pick(self.original, ['nodeset', 'nodesetCaseType', 'nodesetFilter'])));

            self.relevant = uiElement.input().val(self.original.relevant);
            if (self.isTab) {
                self.header.ui.find("input[type='text']").attr("placeholder", gettext("Tab Name"));
                self.relevant.ui.find("input[type='text']").attr("placeholder", gettext("Display Condition"));

                if (self.original.relevant) {
                    self.relevant.observableVal = ko.observable(self.original.relevant);
                    self.relevant.on("change", function () {
                        self.relevant.observableVal(self.relevant.val());
                    });
                }
            }
        }());

        // TODO: use self.field.observableVal instead, and do something similar for header?
        self.header.on("change", function () {
            self.setTileContent();
        });
        self.field.on("change", function () {
            self.setTileContent();
        });
        self.setTileContent();

        self.saveAttempted = ko.observable(false);
        self.useXpathExpression = self.original.useXpathExpression;
        self.showWarning = ko.computed(function () {
            if (self.useXpathExpression) {
                return false;
            }
            if (self.isTab) {
                // Data tab missing its nodeset
                return self.hasNodeset && !self.nodeset_extra.nodesetCaseType() && !self.nodeset_extra.nodeset();
            }
            // Invalid property name
            return (self.field.observableVal() || self.saveAttempted()) && !Utils.isValidPropertyName(self.field.observableVal());
        }, self);

        // Add the graphing option if self is a graph so self we can set the value to graph
        let menuOptions = Utils.getFieldFormats();
        if (self.original.format === "graph") {
            menuOptions = menuOptions.concat([{
                value: "graph",
                label: "",
            }]);
        }

        if (self.useXpathExpression) {
            const menuOptionsToRemove = ['picture', 'audio'];
            for (let i = 0; i < menuOptionsToRemove.length; i++) {
                for (let j = 0; j < menuOptions.length; j++) {
                    if (
                        menuOptions[j].value !== self.original.format
                        && menuOptions[j].value === menuOptionsToRemove[i]
                    ) {
                        menuOptions.splice(j, 1);
                    }
                }
            }
        }

        self.format = uiElement.select(menuOptions).val(self.original.format || null);

        (function () {
            const o = {
                lang: self.lang,
                langs: self.screen.langs,
                module_id: self.screen.config.module_id,
                items: self.original['enum'],
                property_name: self.header,
                multimedia: self.screen.config.multimedia,
                values_are_icons: self.original.format === 'enum-image',
                keys_are_conditions: self.original.format === 'conditional-enum',
            };
            self.enum_extra = uiElement.key_value_mapping(o);
        }());
        const graphConfigurationUiElement = hqImport('app_manager/js/details/graph_config').graphConfigurationUiElement;
        self.graph_extra = graphConfigurationUiElement({
            childCaseTypes: self.screen.childCaseTypes,
            fixtures: self.screen.fixtures,
            lang: self.lang,
            langs: self.screen.langs,
            name: self.header.val(),
        }, self.original.graph_configuration);
        self.header.on("change", function () {
            // The graph should always have the same name as the columnModel
            self.graph_extra.setName(self.header.val());
        });

        const yyyy = new Date().getFullYear(),
            yy = String(yyyy).substring(2);
        self.date_extra = uiElement.select([{
            label: '31/10/' + yy,
            value: '%d/%m/%y',
        }, {
            label: '31/10/' + yyyy,
            value: '%d/%m/%Y',
        }, {
            label: '10/31/' + yyyy,
            value: '%m/%d/%Y',
        }, {
            label: '10/31/' + yy,
            value: '%m/%d/%y',
        }, {
            label: gettext('Oct 31, ') + yyyy,
            value: '%b %d, %Y',
        }]).val(self.original.date_format);
        self.date_extra.ui.prepend($('<div/>').text(gettext(' Format ')));

        self.endpointActionLabel = $('<span>Form to submit on click:</span>');
        const formEndpointOptions = [{value: "-1", label: 'Select a form endpoint'}];
        let moduleName = "";
        const formEndpoints = Object.entries(initialPageData('form_endpoint_options'));
        formEndpoints.forEach(([, endpoint]) => {
            if (endpoint.module_name !== moduleName) {
                moduleName = endpoint.module_name;
                formEndpointOptions.push({groupName: `${moduleName} (${endpoint.module_case_type})`});
            }
            formEndpointOptions.push({value: endpoint.id, label: endpoint.form_name});
        });
        const selectedValue = self.original.endpoint_action_id ? self.original.endpoint_action_id : "-1";
        self.action_form_extra = uiElement.select(formEndpointOptions)
            .val(selectedValue);

        self.late_flag_extra = uiElement.input().val(self.original.late_flag.toString());
        self.late_flag_extra.ui.find('input').css('width', 'auto').css("display", "inline-block");
        self.late_flag_extra.ui.prepend($('<span>' + gettext(' Days late ') + '</span>'));

        self.filter_xpath_extra = uiElement.input().val(self.original.filter_xpath.toString());
        self.filter_xpath_extra.ui.prepend($('<div/>'));

        self.calc_xpath_extra = uiElement.input().val(self.original.calc_xpath.toString());
        self.calc_xpath_extra.ui.prepend($('<div/>'));

        self.time_ago_extra = uiElement.select([{
            label: gettext('Years since date'),
            value: Utils.TIME_AGO.year,
        }, {
            label: gettext('Months since date'),
            value: Utils.TIME_AGO.month,
        }, {
            label: gettext('Weeks since date'),
            value: Utils.TIME_AGO.week,
        }, {
            label: gettext('Days since date'),
            value: Utils.TIME_AGO.day,
        }, {
            label: gettext('Days until date'),
            value: -Utils.TIME_AGO.day,
        }, {
            label: gettext('Weeks until date'),
            value: -Utils.TIME_AGO.week,
        }, {
            label: gettext('Months until date'),
            value: -Utils.TIME_AGO.month,
        }]).val(self.original.time_ago_interval.toString());
        self.time_ago_extra.ui.prepend($('<div/>').text(gettext(' Measuring ')));

        function fireChange() {
            self.fire('change');
        }
        _.each([
            'model',
            'field',
            'header',
            'nodeset_extra',
            'relevant',
            'format',
            'date_extra',
            'enum_extra',
            'action_form_extra',
            'graph_extra',
            'late_flag_extra',
            'filter_xpath_extra',
            'calc_xpath_extra',
            'time_ago_extra',
        ], function (element) {
            self[element].on('change', fireChange);
        });
        self.case_tile_field.subscribe(fireChange);
        self.tileRowStart.subscribe(fireChange);
        self.tileColumnStart.subscribe(fireChange);
        self.tileWidth.subscribe(fireChange);
        self.tileHeight.subscribe(fireChange);
        self.horizontalAlign.subscribe(fireChange);
        self.verticalAlign.subscribe(fireChange);
        self.fontSize.subscribe(fireChange);
        self.showBorder.subscribe(fireChange);
        self.showShading.subscribe(fireChange);

        self.$format = $('<div/>').append(self.format.ui);
        self.$format.find("select").css("margin-bottom", "5px");
        self.format.on('change', function () {
            if (self.field.val() === microCaseImageName && self.format.val() !== 'image') {
                self.field.val('');
                self.field.observableVal('');
                self.field.ui.find('select').val('').change();
                self.field.ui.find('select').prop('disabled', false);
            }

            self.coordinatesVisible(!_.contains(['address', 'address-popup', 'invisible'], self.format.val()));
            // Prevent self from running on page load before init
            if (self.format.ui.parent().length > 0) {
                self.date_extra.ui.detach();
                self.enum_extra.ui.detach();
                self.endpointActionLabel.detach();
                self.action_form_extra.ui.detach();
                self.graph_extra.ui.detach();
                self.late_flag_extra.ui.detach();
                self.filter_xpath_extra.ui.detach();
                self.calc_xpath_extra.ui.detach();
                self.time_ago_extra.ui.detach();
                if (this.val() === "date") {
                    self.format.ui.parent().append(self.date_extra.ui);
                    var format = self.date_extra.ui.find('select');
                    format.change(function () {
                        self.date_extra.value = format.val();
                        fireChange();
                    });
                    self.date_extra.value = format.val();
                } else if (this.val() === "enum" || this.val() === "enum-image" || this.val() === 'conditional-enum') {
                    self.enum_extra.values_are_icons(this.val() === 'enum-image');
                    self.enum_extra.keys_are_conditions(this.val() === 'conditional-enum');
                    self.format.ui.parent().append(self.enum_extra.ui);
                } else if (this.val() === "clickable-icon") {
                    self.enum_extra.values_are_icons(true);
                    self.enum_extra.keys_are_conditions(true);
                    self.format.ui.parent().append(self.enum_extra.ui);
                    self.format.ui.parent().append(self.endpointActionLabel);
                    self.format.ui.parent().append(self.action_form_extra.ui);
                    const actionForm = self.action_form_extra.ui.find('select');
                    actionForm.change(function () {
                        self.action_form_extra.value = actionForm.val();
                        fireChange();
                    });
                    self.action_form_extra.value = actionForm.val();
                } else if (this.val() === "graph") {
                    // Replace format select with edit button
                    var parent = self.format.ui.parent();
                    parent.empty();
                    parent.append(self.graph_extra.ui);
                } else if (this.val() === 'late-flag') {
                    self.format.ui.parent().append(self.late_flag_extra.ui);
                    var input = self.late_flag_extra.ui.find('input');
                    input.change(function () {
                        self.late_flag_extra.value = input.val();
                        fireChange();
                    });
                } else if (this.val() === 'filter') {
                    self.format.ui.parent().append(self.filter_xpath_extra.ui);
                    var filter = self.filter_xpath_extra.ui.find('input');
                    filter.change(function () {
                        self.filter_xpath_extra.value = filter.val();
                        fireChange();
                    });
                } else if (this.val() === 'time-ago') {
                    self.format.ui.parent().append(self.time_ago_extra.ui);
                    var interval = self.time_ago_extra.ui.find('select');
                    interval.change(function () {
                        self.time_ago_extra.value = interval.val();
                        fireChange();
                    });
                } else if (this.val() === 'image') {
                    self.field.ui.find('select').val(microCaseImageName).change();
                    self.field.val(microCaseImageName);
                    self.field.observableVal(microCaseImageName);
                    self.field.ui.find('select').prop('disabled', true);
                }
            }
        }).fire('change');
        // Note self bind to the $edit_view for self google analytics event
        // (as opposed to the format object itself)
        // because self way the events are not fired during the initialization
        // of the page.
        self.format.$edit_view.on("change", function (event) {
            hqImport('analytix/js/google').track.event('Case List Config', 'Display Format', event.target.value);
        });
        self.serialize = function () {
            const column = self.original;
            column.field = self.field.val();
            column.header[self.lang] = self.header.val();
            column.format = self.format.val();
            column.date_format = self.date_extra.val();
            column.enum = self.enum_extra.getItems();
            column.endpoint_action_id = self.action_form_extra.val() === "-1" ? null : self.action_form_extra.val();
            column.grid_x = self.tileColumnStart() - 1;
            column.grid_y = self.tileRowStart() - 1;
            column.height = self.tileHeight();
            column.width = self.tileWidth();
            column.horizontal_align = self.horizontalAlign();
            column.vertical_align = self.verticalAlign();
            column.font_size = self.fontSize();
            column.show_border = self.showBorder();
            column.show_shading = self.showShading();
            column.graph_configuration = self.format.val() === "graph" ? self.graph_extra.val() : null;
            column.late_flag = parseInt(self.late_flag_extra.val(), 10);
            column.time_ago_interval = parseFloat(self.time_ago_extra.val());
            column.filter_xpath = self.filter_xpath_extra.val();
            column.calc_xpath = self.calc_xpath_extra.val();
            column.case_tile_field = self.case_tile_field();
            if (self.isTab) {
                // Note: starting_index is added by screenModel.serialize
                let tab = {
                    header: column.header,
                    isTab: true,
                    starting_index: self.starting_index,
                    relevant: self.relevant.val(),
                    has_nodeset: column.hasNodeset,
                };
                if (column.hasNodeset) {
                    tab = _.extend(tab, {
                        nodeset_case_type: self.nodeset_extra.nodesetCaseType(),
                        nodeset: self.nodeset_extra.nodeset(),
                        nodeset_filter: self.nodeset_extra.nodesetFilter(),
                    });
                }
                return tab;
            }
            return column;
        };
        self.setGrip = function (grip) {
            self.grip = grip;
        };
        self.copyCallback = function () {
            const column = self.serialize();
            // add a marker self self is copied for self purpose
            return JSON.stringify({
                type: 'detail-screen-config:Column',
                contents: column,
            });
        };

        return self;
    };
});
