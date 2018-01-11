hqDefine("reports/js/case_details", function() {
    var EditPropertiesModel = function(options) {
        var self = this;

        self.propertyNames = options.propertyNames || [];   // ordered list of names
        self.properties;                                    // map of name => value

        // If there are a lot of items, make a bigger modal and render properties as columns
        // Supports a small one-column modal, a larger two-column modal, or a full-screen three-column modal
        self.itemsPerPage = 12;
        self.columnsPerPage = Math.min(3, Math.ceil(self.propertyNames.length / self.itemsPerPage));
        self.itemsPerPage *= self.columnsPerPage;
        self.columnClass = "col-sm-" + (12 / self.columnsPerPage);
        self.modalClass = self.columnsPerPage === 3 ? "full-screen-modal" : "";
        self.modalDialogClass = self.columnsPerPage === 2 ? "modal-lg" : "";

        // This modal supports pagination and a search box, all of which is done client-side
        self.currentPage = new ko.observable();
        self.totalPages = new ko.observable();  // observable because it will change if there's a search query
        self.showPagination = self.propertyNames.length > self.itemsPerPage;
        self.query = new ko.observable();

        self.incrementPage = function(increment) {
            var newCurrentPage = self.currentPage() + increment;
            if (newCurrentPage <= 0 || newCurrentPage > self.totalPages()) {
                return;
            }
            self.currentPage(newCurrentPage);
        };

        self.visibleItems = ko.observableArray([]);     // All items visible on the current page
        self.visibleColumns = ko.observableArray([]);   // visibleItems broken down into columns for rendering; an array of arrays

        // Handle pagination and filtering, filling visibleItems with whatever should be on the current page
        // Forces a re-render because it clears and re-fills visibleColumns
        self.render = function() {
            var added = 0,
                index = 0;

            // Remove all items
            self.visibleItems.splice(0);

            // Cycle over all items on previous pages
            while (added < self.itemsPerPage * (self.currentPage() - 1) && index < self.propertyNames.length) {
                if (self.matchesQuery(self.propertyNames[index])) {
                    added++;
                }
                index++;
            }

            // Add as many items as fit on a page
            added = 0;
            while (added < self.itemsPerPage && index < self.propertyNames.length) {
                if (self.matchesQuery(self.propertyNames[index])) {
                    self.visibleItems.push({
                        name: self.propertyNames[index],
                        value: self.properties[self.propertyNames[index]],
                    });
                    added++;
                }
                index++;
            }

            // Break visibleItems into separate columns for rendering
            self.visibleColumns.splice(0);
            var itemsPerColumn = self.itemsPerPage / self.columnsPerPage;
            for (var i = 0; i < self.itemsPerPage; i += itemsPerColumn) {
                self.visibleColumns.push(self.visibleItems.slice(i, i + itemsPerColumn));
            }
        };

        self.query.subscribe(function() {
            self.currentPage(1);
            self.totalPages(Math.ceil(_.filter(self.propertyNames, self.matchesQuery).length / self.itemsPerPage) || 1);
            self.render();
        });

        // Track an array of page numbers, e.g., [1, 2, 3], to render the pagination widget.
        // Having it as an array makes knockout rendering simpler.
        self.visiblePages = ko.observableArray([]);
        self.totalPages.subscribe(function(newValue) {
            self.visiblePages(_.map(_.range(newValue), function(p) { return p + 1; }));
        });

        self.matchesQuery = function(propertyName) {
            return !self.query() || propertyName.indexOf(self.query()) !== -1;
        };

        self.showNoData = ko.computed(function() {
            return self.visibleItems().length === 0;
        });

        self.currentPage.subscribe(self.render);

        self.propertyChange = function(model, e) {
            var $input = $(e.currentTarget);
            self.properties[$input.data('name')] = $input.val();
        };

        self.submitForm = function(model, e) {
            var $button = $(e.currentTarget);
            $button.disableButton();
            $.post({
                url: hqImport("hqwebapp/js/initial_page_data").reverse("edit_case"),
                data: self.properties,
                success: function() {
                    window.location.reload();
                },
                error: function() {
                    hqImport("hqwebapp/js/alert_user").alert_user(gettext('Something unexpected happened. Please try again, or report an issue if the problem persists'), 'danger');
                    $button.enableButton();
                    if (options.error) {
                        options.error.apply();
                    }
                },
            });
            return true;
        };

        self.init = function() {
            self.properties = _.extend({}, options.properties);
            self.query("");
            self.currentPage(1);
            self.render();
        };
        self.init();

        return self;
    };

    $(function() {
        $('#close_case').submit(function() {
            hqImport('analytix/js/google').track.event('Edit Data', 'Close Case', '-', "", {}, function () {
                document.getElementById('close_case').submit();
            });
            return false;
        });

        var initial_page_data = hqImport("hqwebapp/js/initial_page_data").get,
            $editPropertiesModal = $("#edit-dynamic-properties");
        if ($editPropertiesModal.length) {
            $("#edit-dynamic-properties-trigger").click(function() {
                $editPropertiesModal.modal();
            });
            $editPropertiesModal.koApplyBindings(new EditPropertiesModel({
                properties: initial_page_data('dynamic_properties'),
                propertyNames: initial_page_data('dynamic_properties_names'),
                error: function() {
                    $editPropertiesModal.modal('hide');
                },
            }));
        }
    });
});
