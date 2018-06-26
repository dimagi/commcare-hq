hqDefine("reports/js/case_details", function() {
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

        self.received_on = ko.observable(data.received_on);
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
                    var $panel = $("#xform_data_panel");
                    $panel.html(data.html);
                    hqImport("reports/js/single_form").initSingleForm({
                        instance_id: data.xform_id,
                        form_question_map: data.question_response_map,
                        ordered_question_values: data.ordered_question_values,
                        container: $panel,
                    });
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

        var initialPageData = hqImport("hqwebapp/js/initial_page_data");
        hqImport("reports/js/data_corrections").init($("#case-actions .data-corrections-trigger"), $("body > .data-corrections-modal"), {
            properties: initialPageData.get('dynamic_properties'),
            propertyNamesUrl: initialPageData.reverse('case_property_names'),
            saveUrl: initialPageData.reverse("edit_case"),
            analyticsDescriptor: 'Clean Case Data',
        });

        $("#history").koApplyBindings(new XFormListViewModel());

        var $properties = $("#properties");
        if ($properties.length) {
            $properties.koApplyBindings();
        }
    });
});
