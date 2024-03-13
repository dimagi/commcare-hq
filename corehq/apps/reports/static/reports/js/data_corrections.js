/**
 *  UI for data corrections for cases and forms, which is a modal that lists out properties and an editable value
 *  for each. The modal includes a search box (which does client-side filtering only), pagination, and the option
 *  to toggle between different display properties (useful with forms, for toggling between question id and label).
 *  The modal will be sized depending on the number of properties: small, large, or full-screen.
 *
 *  Used with reports/partials/data_corrections_modal.html and a button to trigger the modal.
 *  Usage: dataCorrections.init($triggerElement, $modalElement, options);
 *  Options:
 *      Required:
 *          saveUrl
 *          properties: An object, where keys are the property name and values may be either strings or objects.
 *              If strings, they are assumed to be the property values. If objects, they may include the properties
 *                  value: Required. A string. Space-separated values if this is a multi-select (see below)
 *                  options: Optional. A list of objects, each with a 'text' and 'id' key. If provided, a select
 *                      box with a free text option will be displayed instead of a text box.
 *                  multiple: Optional. If true (and options is provided), a multi-select box with a free text
 *                      option will be displayed instead of a text box.
 *              with the property value and may then have arbitrary other properties to be used for display (see
 *              displayProperties below).
 *      Optional:
 *          propertyNames: All property names, in the order that properties should be displayed.
 *          propertyNamesUrl: Ignore propertyNames and instead fetch that list from this URL.
 *          propertyPrefix: HTML string to display before each property. Rendered as a knockout template that has
 *              access to the property.
 *          propertySuffix: Same idea as proeprtyPrefix.
 *          displayProperties: A list of objects, each with the keys 'property' and 'name'.
 *              Property is the data, plucked from the properties array. Name is displayed in the menu that lets
 *              user toggle between display properties.
 */
hqDefine("reports/js/data_corrections", [
    "jquery",
    "knockout",
    "underscore",
    "hqwebapp/js/assert_properties",
    "analytix/js/kissmetrix",
    "hqwebapp/js/bootstrap3/components.ko",     // pagination
    "select2/dist/js/select2.full.min",
    "hqwebapp/js/bootstrap3/components.ko",    // search box
], function (
    $,
    ko,
    _,
    assertProperties,
    kissAnalytics
) {
    // Represents a single property/value pair, e.g., a form question and its response
    var PropertyModel = function (options) {
        // Don't assert properties of options because PropertyModel allows for
        // arbitrary keys to be used as display properties. Do error if any of
        // these arbitrary keys conflict with existing PropertyModel members.
        var reservedKeys = _.intersection(['dirty'], _.keys(options));
        if (reservedKeys.length) {
            throw new Error("Keys disallowed in PropertyModel: " + reservedKeys.join(", "));
        }

        var self = _.extend({}, options);

        self.name = options.name;
        self.value = ko.observable(options.value || '');
        self.dirty = ko.observable(false);
        self.options = options.options || [];
        self.multiple = options.multiple === undefined ? false : options.multiple;

        // Account for select questions where the value is not one of the given options
        if (self.options.length) {
            if (self.value()) {
                _.each(self.value().split(' '), function (value) {
                    if (!_.find(self.options, function (option) { return value === option.id; })) {
                        self.options.unshift({id: value, text: value});
                    }
                });
            }

            // Single selects need to include a blank option for the allowClear and placeholder options to work
            if (!self.multiple) {
                self.options.unshift({id: '', text: ''});
            }
        }

        // Update hidden value for multiselects. See data_corrections_modal.html for context.
        self.updateSpaceSeparatedValue = function (model, e) {
            var newValue = $(e.currentTarget).val(),
                oldValue = self.value(),
                dirty = self.dirty();

            if (_.isArray(newValue)) {
                oldValue = oldValue ? oldValue.split(" ") : [];
                dirty = dirty || oldValue.length !== newValue.length ||
                        oldValue.length !== _.intersection(oldValue, newValue).length;
                newValue = newValue.join(" ");
            } else {
                dirty = dirty || oldValue !== newValue;
            }
            self.dirty(dirty);
            self.value(newValue);
        };

        return self;
    };

    // Controls the full modal UI
    var DataCorrectionsModel = function (options) {
        assertProperties.assert(options, ['saveUrl', 'properties','$modal'],[
            'propertyNames',
            'propertyNamesUrl',
            'displayProperties',
            'propertyPrefix',
            'propertySuffix',
            'analyticsDescriptor',
        ]);
        var self = {};
        self.$modal = options.$modal;

        // Core data, and the order in which it should be displayed
        self.properties = {};                       // map of name => PropertyModel, populated in init
        self.propertyNames = ko.observableArray();  // populated in init, whether names were provided in options or via ajax

        // Handle modal size: small, large or full-screen, with one, two, or three columns, respectively.
        self.itemsPerColumn = 12;
        self.columnsPerPage = ko.observable(1);
        self.itemsPerPage = ko.observable();
        self.columnClass = ko.observable('');
        self.isFullScreenModal = ko.observable(false);
        self.isLargeModal = ko.observable(false);
        self.propertyNames.subscribe(function (newValue) {
            self.columnsPerPage(Math.min(3, Math.ceil(newValue.length / self.itemsPerColumn)));
            self.columnClass("col-sm-" + (12 / self.columnsPerPage()));
            self.isLargeModal(self.columnsPerPage() === 2);
            self.isFullScreenModal(self.columnsPerPage() === 3);
            self.itemsPerPage(self.itemsPerColumn * self.columnsPerPage());
            self.generateSearchableNames();
        });

        // Support for displaying different property attributes (e.g., name and id)
        self.displayProperties = _.isEmpty(options.displayProperties) ? [{ property: 'name' }] : options.displayProperties;
        self.displayProperty = ko.observable(_.first(self.displayProperties).property);
        self.updateDisplayProperty = function (newValue) {
            self.displayProperty(newValue);
            self.clearQuery();
            self.generateSearchableNames();
        };
        self.breakWord = function (str) {
            // Break words on slashes (as in question paths) or underscores (as in case properties and also questions)
            // Don't break on slashes that are present because they're in an HTML end tag
            return str.replace(/([^<]\s*[\/_])/g, "$1\u200B");     // eslint-disable-line no-useless-escape
        };
        var innerTemplate = _.map(self.displayProperties, function (p) {
            return _.template("<span data-bind='html: $root.breakWord(<%= property %>), visible: $root.displayProperty() === \"<%= property %>\"'></span>")(p);
        }).join("");
        self.propertyTemplate = {
            nodes: $("<div>" + (options.propertyPrefix || "") + innerTemplate + (options.propertySuffix || "") + "</div>"),
        };

        // Draw items on the current page, taking into account pagination and searching.
        // visibleItems is a list of whichever properties should be displayed on the current page.
        // visibleColumns is a list of lists: the same properties, but organized into columns
        // to simplify the knockout template.
        self.visibleItems = ko.observableArray([]);
        self.visibleColumns = ko.observableArray([]);
        self.render = function () {
            var added = 0,
                index = 0;

            // Remove all items
            self.visibleItems.splice(0);

            // Cycle over all items on previous pages
            while (added < self.itemsPerPage() * (self.currentPage() - 1) && index < self.propertyNames().length) {
                if (self.matchesQuery(self.searchableNames[index])) {
                    added++;
                }
                index++;
            }

            // Add as many items as fit on a page
            added = 0;
            while (added < self.itemsPerPage() && index < self.propertyNames().length) {
                if (self.matchesQuery(self.searchableNames[index])) {
                    var name = self.propertyNames()[index];
                    if (!self.properties[name]) {
                        self.properties[name] = new PropertyModel({ name: name });
                    }
                    self.visibleItems.push(self.properties[name]);
                    added++;
                }
                index++;
            }

            // Break visibleItems into separate columns for rendering
            self.visibleColumns.splice(0);
            var itemsPerColumn = self.itemsPerPage() / self.columnsPerPage();
            for (var i = 0; i < self.itemsPerPage(); i += itemsPerColumn) {
                self.visibleColumns.push(self.visibleItems.slice(i, i + itemsPerColumn));
            }
        };

        // Search
        self.query = ko.observable();
        self.matchesQuery = function (propertyName) {
            return !self.query() || propertyName.toLowerCase().indexOf(self.query().toLowerCase()) !== -1;
        };
        self.filter = function (initial) {
            self.currentPage(1);
            self.totalFilteredItems(Math.ceil(_.filter(self.searchableNames, self.matchesQuery).length) || 1);
            self.render();
            if (!initial) {
                setupSelect2(self.$modal);
            }
        };
        self.clearQuery = function (initial) {
            self.query('');
            self.filter(initial);
        };

        // Because of how search is implemented, it's useful to store a list of the values that we're going to
        // search against, ordered the same way properties are displayed. Regenerate this list each time
        // the current display property changes.
        self.searchableNames = [];
        self.generateSearchableNames = function () {
            if (self.displayProperty() === 'name') {
                self.searchableNames = self.propertyNames();
            } else {
                var displayPropertyObj = _.findWhere(self.displayProperties, { property: self.displayProperty() }),
                    search = displayPropertyObj.search || displayPropertyObj.property;
                self.searchableNames = [];
                _.each(self.propertyNames(), function (name) {
                    if (self.properties[name]) {
                        self.searchableNames.push(self.properties[name][search]);
                    }
                });
            }
        };

        // Pagination
        self.currentPage = ko.observable();
        self.totalFilteredItems = ko.observable();
        self.totalItems = ko.computed(function () {  // how many items to display in pagination
            return self.query() ? self.totalFilteredItems() : self.propertyNames().length;
        });
        self.currentPage.subscribe(self.render);

        // Saving
        self.submitForm = function (model, e) {
            var $button = $(e.currentTarget);
            $button.disableButton();

            // Filter properties to those that are dirty, and transform to name => value object
            var properties = _.chain(self.properties)
                .filter(function (prop) { return prop.dirty(); })
                .indexBy('name')
                .mapObject(function (model) { return model.value(); })
                .value();
            $.post({
                url: options.saveUrl,
                data: {
                    properties: JSON.stringify(properties),
                },
                success: function () {
                    window.location.reload();
                },
                error: function () {
                    $button.enableButton();
                    self.showRetry(true);
                },
            });
            return true;
        };

        // Analytics
        self.analyticsDescriptor = options.analyticsDescriptor;
        self.trackOpen = function () {
            if (self.analyticsDescriptor) {
                kissAnalytics.track.event("Clicked " + self.analyticsDescriptor + " Button");
            }
        };
        self.trackSave = function () {
            if (self.analyticsDescriptor) {
                kissAnalytics.track.event("Clicked Save on " + self.analyticsDescriptor + " Modal");
            }
        };

        // Control visibility around loading (spinner is shown if names are fetched via ajax) and error handling.
        self.showSpinner = ko.observable(true);
        self.showPagination = ko.computed(function () {
            return !self.showSpinner() && self.propertyNames().length > self.itemsPerPage();
        });
        self.showError = ko.observable(false);
        self.showRetry = ko.observable(false);
        self.disallowSave = ko.computed(function () {
            return self.showSpinner() || self.showError();
        });
        self.showNoData = ko.computed(function () {
            return !self.showError() && self.visibleItems().length === 0;
        });

        // Setup to do once property names exist
        self.init = function () {
            self.properties = _.extend({}, _.mapObject(options.properties, function (data, name) {
                if (typeof(data) === "string") {
                    data = { value: data };
                }
                return new PropertyModel(_.extend({}, data, {
                    name: name,
                    value: data.value,
                    display: _.without(data, 'name', 'value'),
                }));
            }));
            self.generateSearchableNames();
            self.clearQuery(true);
            self.currentPage(1);
            self.showError(false);
            self.showRetry(false);
            self.render();
        };

        // Initialization: fetch property names if needed
        var _loadPropertyNames = function (names) {
            _.each(names, function (name) {
                self.propertyNames.push(name);
            });
            self.showSpinner(false);
            self.init();
        };
        if (options.propertyNamesUrl) {
            $.get({
                url: options.propertyNamesUrl,
                success: _loadPropertyNames,
                error: function () {
                    self.showSpinner(false);
                    self.showError(true);
                },
            });
        } else {
            _loadPropertyNames(options.propertyNames || _.keys(options.properties));
        }

        return self;
    };

    var init = function ($trigger, $modal, options) {
        var model = undefined;
        if ($trigger.length && $modal.length) {
            options.$modal = $modal;
            model = DataCorrectionsModel(options);
            $modal.koApplyBindings(model);
            $trigger.click(function () {
                $modal.modal();
                setupSelect2($modal);

            });
        }
        return model;
    };

    var setupSelect2 = function ($modal) {
        $modal.find(".modal-body select").each(function () {
            var $el = $(this),
                multiple = !!$el.attr("multiple"),
                select2Options = {
                    width: '100%',
                    tags: true,
                };
            if (!multiple) {
                // Allow clearing in a single select, including adding a blank option
                // so placeholder and allowClear work properly
                select2Options = _.extend(select2Options, {
                    allowClear: true,
                    placeholder: gettext('Select a value'),
                    dropdownParent: $modal,
                });
            }
            $el.select2(select2Options);
            if (multiple) {
                var $input = $el.siblings("input");
                $el.val($input.val().split(" ")).trigger("change");
            }
        });
    };

    return {
        init: init,
    };
});
