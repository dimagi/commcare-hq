/**
 *  UI for data corrections for cases and forms, which is a modal that lists out properties and an editable value
 *  for each. The modal includes a search box (which does client-side filtering only), pagination, and the option
 *  to toggle between different display properties (useful with forms, for toggling between question id and label).
 *  The modal will be sized depending on the number of properties: small, large, or full-screen.
 *
 *  Used with reports/partials/data_corrections_trigger.html and reports/partials/data_corrections_modal.html
 *  Usage: hqImport("reports/js/data_corrections").init($triggerElement, $modalElement, options);
 *  Options:
 *      Required:
 *          saveUrl
 *          properties: An object, where keys are the property name and values may be either strings or objects.
 *              If strings, they are assumed to be the property values. If objects, they should have a 'value' key
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
hqDefine("reports/js/data_corrections", function() {
    // Represents a single property/value pair, e.g., a form question and its response
    var PropertyModel = function(options) {
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

        return self;
    };

    // Controls the full modal UI
    var DataCorrectionsModel = function(options) {
        hqImport("hqwebapp/js/assert_properties").assert(options, ['saveUrl', 'properties'],
            ['propertyNames', 'propertyNamesUrl', 'displayProperties', 'propertyPrefix', 'propertySuffix']);
        var self = {};

        // Core data, and the order in which it should be displayed
        self.properties = {};                       // map of name => PropertyModel, populated in init
        self.propertyNames = ko.observableArray();  // populated in init, whether names were provided in options or via ajax

        // Handle modal size: small, large or full-screen, with one, two, or three columns, respectively.
        self.itemsPerColumn = 12;
        self.columnsPerPage = ko.observable(1);
        self.itemsPerPage = ko.computed(function() {
            return self.itemsPerColumn * self.columnsPerPage();
        });
        self.columnClass = ko.observable('');
        self.isFullScreenModal = ko.observable(false);
        self.isLargeModal = ko.observable(false);
        self.propertyNames.subscribe(function(newValue) {
            self.columnsPerPage(Math.min(3, Math.ceil(newValue.length / self.itemsPerColumn)));
            self.columnClass("col-sm-" + (12 / self.columnsPerPage()));
            self.isLargeModal(self.columnsPerPage() === 2);
            self.isFullScreenModal(self.columnsPerPage() === 3);
            self.generateSearchableNames();
        });

        // Support for displaying different property attributes (e.g., name and id)
        self.displayProperties = _.isEmpty(options.displayProperties) ? [{ property: 'name' }] : options.displayProperties;
        self.displayProperty = ko.observable(_.first(self.displayProperties).property);
        self.updateDisplayProperty = function(newValue) {
            self.displayProperty(newValue);
            self.initQuery();
            self.generateSearchableNames();
        };
        self.breakWord = function(str) {
            return str.replace(/([\/_])/g, "$1\u200B");     // eslint-disable-line no-useless-escape
        };
        var innerTemplate = _.map(self.displayProperties, function(p) {
            return _.template("<span data-bind='text: $root.breakWord(<%= property %>), visible: $root.displayProperty() === \"<%= property %>\"'></span>")(p);
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
        self.render = function() {
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

        // Pagination
        self.currentPage = ko.observable();
        self.totalPages = ko.observable();  // observable because it will change if there's a search query
        self.incrementPage = function(increment) {
            var newCurrentPage = self.currentPage() + increment;
            if (newCurrentPage <= 0 || newCurrentPage > self.totalPages()) {
                return;
            }
            self.currentPage(newCurrentPage);
        };

        // Track an array of page numbers, e.g., [1, 2, 3], used by the pagination UI.
        // Having it as an array makes knockout rendering simpler.
        self.visiblePages = ko.observableArray([]);
        self.totalPages.subscribe(function(newValue) {
            self.visiblePages(_.map(_.range(newValue), function(p) { return p + 1; }));
        });
        self.currentPage.subscribe(self.render);

        // Search
        self.query = ko.observable();
        self.matchesQuery = function(propertyName) {
            return !self.query() || propertyName.toLowerCase().indexOf(self.query().toLowerCase()) !== -1;
        };
        self.initQuery = function() {
            self.query("");
        };
        self.query.subscribe(function() {
            self.currentPage(1);
            self.totalPages(Math.ceil(_.filter(self.searchableNames, self.matchesQuery).length / self.itemsPerPage()) || 1);
            self.render();
        });

        // Because of how search is implemented, it's useful to store a list of the values that we're going to
        // search against, ordered the same way properties are displayed. Regenerate this list each time
        // the current display property changes.
        self.searchableNames = [];
        self.generateSearchableNames = function() {
            if (self.displayProperty() === 'name') {
                self.searchableNames = self.propertyNames();
            } else {
                var displayPropertyObj = _.findWhere(self.displayProperties, { property: self.displayProperty() }),
                    search = displayPropertyObj.search || displayPropertyObj.property;
                self.searchableNames = [];
                _.each(self.propertyNames(), function(name) {
                    if (self.properties[name]) {
                        self.searchableNames.push(self.properties[name][search]);
                    }
                });
            }
        };

        // Saving
        self.submitForm = function(model, e) {
            var $button = $(e.currentTarget);
            $button.disableButton();
            $.post({
                url: options.saveUrl,
                data: _.mapObject(self.properties, function(model) {
                    return model.value();
                }),
                success: function() {
                    window.location.reload();
                },
                error: function() {
                    $button.enableButton();
                    self.showRetry(true);
                },
            });
            return true;
        };

        // Control visibility around loading (spinner is shown if names are fetched via ajax) and error handling.
        self.showSpinner = ko.observable(true);
        self.showPagination = ko.computed(function() {
            return !self.showSpinner() && self.propertyNames().length > self.itemsPerPage();
        });
        self.showError = ko.observable(false);
        self.showRetry = ko.observable(false);
        self.disallowSave = ko.computed(function() {
            return self.showSpinner() || self.showError();
        });
        self.showNoData = ko.computed(function() {
            return !self.showError() && self.visibleItems().length === 0;
        });

        // Setup to do once property names exist
        self.init = function() {
            self.properties = _.extend({}, _.mapObject(options.properties, function(data, name) {
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
            self.initQuery();
            self.currentPage(1);
            self.showError(false);
            self.showRetry(false);
            self.render();
        };

        // Initialization: fetch property names if needed
        var _loadPropertyNames = function(names) {
            _.each(names, function(name) {
                self.propertyNames.push(name);
            });
            self.showSpinner(false);
            self.init();
        };
        if (options.propertyNamesUrl) {
            $.get({
                url: options.propertyNamesUrl,
                success: _loadPropertyNames,
                error: function() {
                    self.showSpinner(false);
                    self.showError(true);
                },
            });
        } else {
            _loadPropertyNames(options.propertyNames || _.keys(options.properties));
        }

        return self;
    };

    var init = function($trigger, $modal, options) {
        var model = undefined;
        if ($trigger.length && $modal.length) {
            $trigger.click(function() {
                $modal.modal();
            });
            model = new DataCorrectionsModel(options);
            $modal.koApplyBindings(model);
        }
        return model;
    };

    return {
        init: init,
    };
});
