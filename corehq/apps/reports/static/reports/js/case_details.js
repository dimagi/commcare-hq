hqDefine("reports/js/case_details", function() {
    var EditPropertiesModel = function(options) {
        var self = this;

        self.propertyNames = ko.observableArray();  // ordered list of names, populated by ajax call because it's slow
        self.properties;                            // map of name => value

        // If there are a lot of items, make a bigger modal and render properties as columns
        // Supports a small one-column modal, a larger two-column modal, or a full-screen three-column modal
        self.itemsPerColumn = 12;
        self.columnsPerPage = ko.observable(1);
        self.itemsPerPage = ko.computed(function() {
            return self.itemsPerColumn * self.columnsPerPage();
        });
        self.columnClass = ko.observable('');
        self.modalClass = ko.observable('');
        self.modalDialogClass = ko.observable('');
        self.propertyNames.subscribe(function(newValue) {
            self.columnsPerPage(Math.min(3, Math.ceil(newValue.length / self.itemsPerColumn)));
            self.columnClass("col-sm-" + (12 / self.columnsPerPage()));
            self.modalClass(self.columnsPerPage() === 3 ? "full-screen-modal" : "");
            self.modalDialogClass(self.columnsPerPage() === 2 ? "modal-lg" : "");
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
                    self.visibleItems.push({
                        name: self.propertyNames()[index],
                        value: self.properties[self.propertyNames()[index]],
                    });
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
                    $button.enableButton();
                    self.showRetry(true);
                },
            });
            return true;
        };

        self.init = function() {
            self.properties = _.extend({}, options.properties);
            self.initQuery();
            self.currentPage(1);
            self.render();
        };

        $.get({
            url: hqImport("hqwebapp/js/initial_page_data").reverse('case_property_names'),
            success: function(names) {
                _.each(names, function(name) {
                    self.propertyNames.push(name);
                });
                self.showSpinner(false);
                self.init();
            },
            error: function() {
                self.showSpinner(false);
                self.showError(true);
            },
        });

        return self;
    };

    var XFormDataModel = function(data) {
        var self = this;
        self.id = ko.observable(data.id);


        self.format_user = function(username) {
            if (username === undefined || username === null) {
                return gettext("Unknown");
            }
            return username.split('@')[0];
        };

        self.pad_zero = function(val) {
            if (val < 10) {
                return "0" + val;
            }
            return val;
        };

        self.format_date = function(isodatestring) {
            if (!isodatestring) {
                return gettext('present');
            }
            //parse and format the date timestamps - seconds since epoch into date object
            var date = new Date(isodatestring.split('+')[0]);

            // Get the TZ offset based the project's timezone and create a new date
            // object with that as it's "UTC" date
            var _configuredTZOffset = hqImport("hqwebapp/js/initial_page_data").get('timezone_offset');
            date = new Date(date.getTime() + _configuredTZOffset);

            // hours part from the timestamp
            var hours = self.pad_zero(date.getUTCHours());
            // minutes part from the timestamp
            var minutes = self.pad_zero(date.getUTCMinutes());

            var year = date.getUTCFullYear();
            var month = date.getUTCMonth() + 1;
            var day = date.getUTCDate();

            return  year + '-' + month + '-' + day + ' ' + hours + ":" + minutes;
        };

        self.received_on = ko.observable(self.format_date(data.received_on));
        self.userID = ko.observable(data.user.id);
        self.username = ko.observable(self.format_user(data.user.username));
        self.readable_name = ko.observable(data.readable_name);
    };

    var XFormListViewModel = function() {
        var self = this;

        self.pagination_options = [10,25,50,100];

        self.xforms = ko.observableArray([]);
        self.page_size = ko.observable(10);
        self.disp_page_index = ko.observable(1);
        self.total_rows = ko.observable(-1);
        self.selected_xform_idx = ko.observable(-1);
        self.selected_xform_doc_id = ko.observable("");
        self.selected_xforms = ko.observableArray([]);

        self.form_type_facets = ko.observableArray([]);
        self.form_recv_facets = ko.observableArray([]);

        self.data_loading = ko.observable(false);

        self.getParameterByName = function(name, url) {
            if (!url) url = window.location.href;
            name = name.replace(/[\[\]]/g, "\\$&");
            var regex = new RegExp("[?&]" + name + "(=([^&#]*)|&|#|$)"),
                results = regex.exec(url);
            if (!results) return null;
            if (!results[2]) return '';
            return decodeURIComponent(results[2].replace(/\+/g, " "));
        };

        var api_url = hqImport("hqwebapp/js/initial_page_data").get('xform_api_url');
        var init = function() {
            var hash = window.location.hash.split('?');
            if (hash[0] !== '#!history') {
                return;
            }

            var formId = self.getParameterByName('form_id', window.location.hash);
            if (formId) {
                self.get_xform_data(formId);
                self.selected_xform_doc_id(formId);
            }
        };

        self.get_xform_data = function(xform_id) {
            $.cachedAjax({
                "type": "GET",
                "url": hqImport("hqwebapp/js/initial_page_data").reverse('case_form_data', xform_id),
                "success": function(data) {
                    $("#xform_data_panel").html(data);
                },
            });
        };

        init();

        self.xform_history_cb = function(data) {
            self.total_rows(hqImport("hqwebapp/js/initial_page_data").get('xform_ids').length);
            var mapped_xforms = $.map(data, function (item) {
                return new XFormDataModel(item);
            });
            self.xforms(mapped_xforms);
            var xformId = self.selected_xform_doc_id();
            if (xformId) {
                self.selected_xform_idx(self.xforms.indexOf());
            } else {
                self.selected_xform_idx(-1);
            }
        };

        self.all_rows_loaded = ko.computed(function() {
            return self.total_rows() === self.xforms().length;
        });

        self.page_count = ko.computed(function() {
            return Math.ceil(self.total_rows()/self.page_size());
        });

        self.refresh_forms = ko.computed(function () {
            var disp_index = self.disp_page_index();
            if (disp_index > self.page_count.peek()) {
                self.disp_page_index(self.page_count.peek());
                return;
            }
            if (self.total_rows.peek() > 0 && self.all_rows_loaded.peek()) {
                return;
            }
            self.data_loading(true);
            var start_num = disp_index || 1;
            var start_range = (start_num - 1) * self.page_size();
            var end_range = start_range + self.page_size();
            $.ajax({
                "type": "GET",
                "url":  api_url,
                "data": {
                    'start_range': start_range,
                    'end_range': end_range,
                },
                "success": function(data) {
                    self.xform_history_cb(data);
                },
                "complete": function() {
                    self.data_loading(false);
                },
            });
        }, this).extend({deferred: true});

        self.nextPage = function() {
            self.disp_page_index(self.disp_page_index() + 1);
        };

        self.prevPage = function() {
            self.disp_page_index(self.disp_page_index() - 1);
        };

        self.clickRow = function(item) {
            $("#xform_data_panel").html("<img src='/static/hqwebapp/images/ajax-loader.gif' alt='loading indicator' />");
            var idx = self.xforms().indexOf(item);

            self.get_xform_data(self.xforms()[idx].id());
            self.selected_xform_idx(idx);
            self.selected_xform_doc_id(self.xforms()[idx].id());
            if (idx > -1) {
                self.selected_xforms([]);
                self.selected_xforms.push(self.xforms()[self.selected_xform_idx()]);
            }
            window.history.pushState({}, '', '#!history?form_id=' + self.selected_xform_doc_id());
        };

        self.page_start_num = ko.computed(function() {
            var start_num = self.disp_page_index() || 1;
            var calc_start_num = ((start_num - 1) * self.page_size()) + 1;
            return calc_start_num;
        });

        self.page_end_num = ko.computed(function() {
            var start_num = self.disp_page_index() || 1;
            var end_page_num = ((start_num - 1) * self.page_size()) + self.page_size();
            if (end_page_num > self.total_rows()) {
                return self.total_rows();
            }
            else {
                return end_page_num;
            }
        });

        self.all_pages = function() {
            return _.range(1, self.page_count()+1);
        };

        self.xform_view = ko.computed(function () {
            return self.selected_xform_doc_id() !== undefined;
        });

        self.row_highlight = ko.computed(function() {
            //hitting next page will not disappear the xform display just remove the highlight
            if (self.selected_xform_idx() === -1) {
                return false;
            } else  {
                if (self.selected_xforms[0] !== undefined) {
                    return self.selected_xform_doc_id() === self.selected_xforms()[0].id();
                } else {
                    return true;
                }
            }
        });
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
            }));
        }

        $("#history").koApplyBindings(new XFormListViewModel());

        var $properties = $("#properties");
        if ($properties.length) {
            $properties.koApplyBindings();
        }
    });
});
