hqDefine("reports/js/data_corrections", function() {
    var PropertyModel = function(options) {
        var self = options;

        self.name = options.name;
        self.value = ko.observable(options.value || '');
        self.dirty = ko.observable(false);

        return self;
    };

    var DataCorrectionsModel = function(options) {
        var self = this;

        self.url = options.url;
        self.saveUrl = options.saveUrl;
        self.propertyTemplate = {
            // TODO: make icons blue, like in readable form, and make text less bold
            nodes: $("<div>" + (options.propertyTemplate || "<span data-bind='text: name'></span>" )+ "</div>"),
        };
        self.displayProperty = ko.observable(options.displayProperty || '');
        self.propertyNames = ko.observableArray();  // ordered list of names, sometimes populated by ajax call because it's slow
        self.properties = {};                       // map of name => PropertyModel, populated in init

        self.updateDisplayProperty = function(model, e) {
            self.displayProperty($(e.currentTarget).data("display"));
        };

        // If there are a lot of items, make a bigger modal and render properties as columns
        // Supports a small one-column modal, a larger two-column modal, or a full-screen three-column modal
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
        });

        // This modal supports pagination and a search box, all of which is done client-side
        self.currentPage = ko.observable();
        self.totalPages = ko.observable();  // observable because it will change if there's a search query
        self.query = ko.observable();

        self.showSpinner = ko.observable(true);
        self.showPagination = ko.computed(function() {
            return !self.showSpinner() && self.propertyNames().length > self.itemsPerPage();
        });
        self.showError = ko.observable(false);
        self.showRetry = ko.observable(false);
        self.disallowSave = ko.computed(function() {
            return self.showSpinner() || self.showError();
        });

        self.incrementPage = function(increment) {
            var newCurrentPage = self.currentPage() + increment;
            if (newCurrentPage <= 0 || newCurrentPage > self.totalPages()) {
                return;
            }
            self.currentPage(newCurrentPage);
        };

        self.visibleItems = ko.observableArray([]);     // All items visible on the current page
        self.visibleColumns = ko.observableArray([]);   // visibleItems broken down into columns for rendering; an array of arrays

        self.showNoData = ko.computed(function() {
            return !self.showError() && self.visibleItems().length === 0;
        });

        // Handle pagination and filtering, filling visibleItems with whatever should be on the current page
        // Forces a re-render because it clears and re-fills visibleColumns
        self.render = function() {
            var added = 0,
                index = 0;

            // Remove all items
            self.visibleItems.splice(0);

            // Cycle over all items on previous pages
            while (added < self.itemsPerPage() * (self.currentPage() - 1) && index < self.propertyNames().length) {
                if (self.matchesQuery(self.propertyNames()[index])) {
                    added++;
                }
                index++;
            }

            // Add as many items as fit on a page
            added = 0;
            while (added < self.itemsPerPage() && index < self.propertyNames().length) {
                if (self.matchesQuery(self.propertyNames()[index])) {
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

        self.initQuery = function() {
            self.query("");
        };

        self.query.subscribe(function() {
            self.currentPage(1);
            self.totalPages(Math.ceil(_.filter(self.propertyNames(), self.matchesQuery).length / self.itemsPerPage()) || 1);
            self.render();
        });

        // Track an array of page numbers, e.g., [1, 2, 3], to render the pagination widget.
        // Having it as an array makes knockout rendering simpler.
        self.visiblePages = ko.observableArray([]);
        self.totalPages.subscribe(function(newValue) {
            self.visiblePages(_.map(_.range(newValue), function(p) { return p + 1; }));
        });

        self.matchesQuery = function(propertyName) {
            return !self.query() || propertyName.toLowerCase().indexOf(self.query().toLowerCase()) !== -1;
        };

        self.currentPage.subscribe(self.render);

        self.submitForm = function(model, e) {
            var $button = $(e.currentTarget);
            $button.disableButton();
            $.post({
                url: self.saveUrl,
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

        self.init = function() {
            self.properties = _.extend({}, _.mapObject(options.properties, function(data, name) {
                if (typeof(data) === "string") {
                    data = { value: data };
                }
                return new PropertyModel(_.extend({}, data, {
                    name: name,
                }));
            }));
            self.initQuery();
            self.currentPage(1);
            self.showError(false);
            self.showRetry(false);
            self.render();
        };

        var _success = function(names) {
            _.each(names, function(name) {
                self.propertyNames.push(name);
            });
            self.showSpinner(false);
            self.init();
        };
        if (self.url) {
            $.get({
                url: self.url,
                success: _success,
                error: function() {
                    self.showSpinner(false);
                    self.showError(true);
                },
            });
        } else {
            _success(options.propertyNames || _.keys(options.properties));
        }

        return self;
    };

    var init = function($trigger, $modal, options) {
        if ($trigger.length && $modal.length) {
            $trigger.click(function() {
                $modal.modal();
            });
            $modal.koApplyBindings(new DataCorrectionsModel(options));
        }
    };

    return {
        init: init,
    };
});
