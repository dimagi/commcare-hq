hqDefine("reports/js/case_details", [
    'jquery',
    'knockout',
    'underscore',
    'clipboard/dist/clipboard',
    'hqwebapp/js/initial_page_data',
    'analytix/js/google',
    'case/js/case_property_modal',
    'reports/js/data_corrections',
    'reports/js/single_form',
    'case/js/case_hierarchy',
    'reports/js/readable_form',
    'jquery-memoized-ajax/jquery.memoized.ajax.min',
], function(
    $,
    ko,
    _,
    Clipboard,
    initialPageData,
    googleAnalytics,
    casePropertyModal,
    dataCorrections,
    singleForm
) {
    var xformDataModel = function(data) {
        var self = {};
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

        return self;
    };

    var xformListViewModel = function() {
        var self = {};

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
            name = name.replace(/[[\]]/g, "\\$&");
            var regex = new RegExp("[?&]" + name + "(=([^&#]*)|&|#|$)"),
                results = regex.exec(url);
            if (!results) return null;
            if (!results[2]) return '';
            return decodeURIComponent(results[2].replace(/\+/g, " "));
        };

        var apiUrl = initialPageData.get('xform_api_url');
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

        self.get_xform_data = function(xformId) {
            $.memoizedAjax({
                "type": "GET",
                "url": initialPageData.reverse('case_form_data', xformId),
                "success": function(data) {
                    var $panel = $("#xform_data_panel");
                    $panel.html(data.html);
                    singleForm.initSingleForm({
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
            self.total_rows(initialPageData.get('xform_ids').length);
            var mappedXforms = $.map(data, function (item) {
                return xformDataModel(item);
            });
            self.xforms(mappedXforms);
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
            var dispIndex = self.disp_page_index();
            if (dispIndex > self.page_count.peek()) {
                self.disp_page_index(self.page_count.peek());
                return;
            }
            if (self.total_rows.peek() > 0 && self.all_rows_loaded.peek()) {
                return;
            }
            self.data_loading(true);
            var startNum = dispIndex || 1;
            var startRange = (startNum - 1) * self.page_size();
            var endRange = startRange + self.page_size();
            $.ajax({
                "type": "GET",
                "url":  apiUrl,
                "data": {
                    'start_range': startRange,
                    'end_range': endRange,
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
            var startNum = self.disp_page_index() || 1;
            var calcStartNum = ((startNum - 1) * self.page_size()) + 1;
            return calcStartNum;
        });

        self.page_end_num = ko.computed(function() {
            var startNum = self.disp_page_index() || 1;
            var endPageNum = ((startNum - 1) * self.page_size()) + self.page_size();
            if (endPageNum > self.total_rows()) {
                return self.total_rows();
            }
            else {
                return endPageNum;
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

        return self;
    };

    $(function() {
        $('#close_case').submit(function() {
            googleAnalytics.track.event('Edit Data', 'Close Case', '-', "", {}, function () {
                document.getElementById('close_case').submit();
            });
            return false;
        });

        // Data cleaning
        dataCorrections.init($("#case-actions .data-corrections-trigger"), $("body > .data-corrections-modal"), {
            properties: initialPageData.get('dynamic_properties'),
            propertyNamesUrl: initialPageData.reverse('case_property_names'),
            saveUrl: initialPageData.reverse("edit_case"),
            analyticsDescriptor: 'Clean Case Data',
        });

        $("#history").koApplyBindings(xformListViewModel());

        var $properties = $("#properties");
        if ($properties.length) {
            $properties.koApplyBindings();
        }

        // Case property history modal
        var $casePropertyNames = $("a.case-property-name"),
            $propertiesModal = $("#case-properties-modal"),
            modalData = casePropertyModal.casePropertyModal();
        $propertiesModal.koApplyBindings(modalData);
        $casePropertyNames.click(function(){
            modalData.init($(this).data('property-name'));
            $propertiesModal.modal();
        });

        // Tab history
        // Modified from https://gist.github.com/josheinstein/5586469
        if (location.hash.substr(0,2) === "#!") {
            var hash = location.hash.substr(2);
            hash = hash.split('?')[0];
            $("a[href='#" + hash + "']").tab("show");
        }
        $("a[data-toggle='tab']").on("shown", function (e) {
            var hash = $(e.target).attr("href");
            if (hash.substr(0,1) === "#") {
                location.replace("#!" + hash.substr(1));
            }
        });
    });
});
