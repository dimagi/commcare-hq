$(function () {
    $("#history").koApplyBindings(new XFormListViewModel());
});

function pad_zero(val) {
    if (val < 10) {
        return "0" + val;
    } else {
        return val;
    }
}

function format_date(isodatestring) {
    if (isodatestring == "" || isodatestring == null) {
        return 'present';
    }
    //parse nad format the date timestamps - seconds since epoch into date object
    var date = new Date(isodatestring.split('+')[0]);

    // Get the TZ offset based the project's timezone and create a new date
    // object with that as it's "UTC" date
    var _configuredTZOffset = CASE_DETAILS.timezone_offset;
    date = new Date(date.getTime() + _configuredTZOffset);

    // hours part from the timestamp
    var hours = pad_zero(date.getUTCHours());
    // minutes part from the timestamp
    var minutes = pad_zero(date.getUTCMinutes());

    // seconds part from the timestamp
    var seconds = pad_zero(date.getUTCSeconds());

    var year = date.getUTCFullYear();
    var month = date.getUTCMonth() + 1;
    var day = date.getUTCDate();

    //return  year + '/' + month + '/' + day + ' ' + hours + ':' + minutes + ':' + second_str;
    //return  year + '/' + month + '/' + day;
    return  year + '-' + month + '-' + day + ' ' + hours + ":" + minutes;

}

function format_user(username) {
    if (username === undefined || username === null) {
        return "Unknown";
    }
    else {
        return username.split('@')[0];
    }
}

function XFormDataModel(data) {
    var self = this;
    self.id = ko.observable(data.id);
    self.received_on = ko.observable(format_date(data.received_on));
    self.userID = ko.observable(data.user.id);
    self.username = ko.observable(format_user(data.user.username));
    self.readable_name = ko.observable(data.readable_name);
};

function FormTypeFacetModel(data) {
    var self = this;
    //{"form_type_facets": {"_type": "terms", "total": 854, "terms": [{"count": 605, "term": "dots_form"}, {"count": 168, "term": "data"}, {"count": 75, "term": "progress_note"}, {"count": 6, "term": "bloodwork"}], "other": 0, "missing": 0},
    self.form_name = ko.observable(data.term);
    self.form_count = ko.observable(data.count);
};

function FormDateHistogram(data) {
    var self = this;
    self.es_time = ko.observable(data.time);
    self.form_count = ko.observable(data.count);
};

function getParameterByName(name, url) {
    if (!url) url = window.location.href;
    name = name.replace(/[\[\]]/g, "\\$&");
    var regex = new RegExp("[?&]" + name + "(=([^&#]*)|&|#|$)"),
        results = regex.exec(url);
    if (!results) return null;
    if (!results[2]) return '';
    return decodeURIComponent(results[2].replace(/\+/g, " "));
}

function XFormListViewModel() {
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

    var api_url = CASE_DETAILS.xform_api_url;


    var init = function() {
        var hash = window.location.hash.split('?');
        if (hash[0] !== '#!history') {
            return;
        }

        var formId = getParameterByName('form_id', window.location.hash);
        if (formId) {
            self.get_xform_data(formId);
            self.selected_xform_doc_id(formId);
        }
    };

    self.get_xform_data = function(xform_id) {
        //method for getting individual xform via GET
        $.cachedAjax({
            "type": "GET",
            "url": CASE_DETAILS.xform_ajax_url + xform_id + "/",
            "success": function(data) {
                $("#xform_data_panel").html(data);
                //$("#xform_data_panel").html('<h2>selected ' + xform_id + "</h2>");
            },
            "error": function(data) {
                console.log("get xform error");
                console.log(data);
            },
            "complete": function(data) {
            }
        })
    };

    init();

    self.xform_history_cb = function(data) {
        self.total_rows(CASE_DETAILS.xform_ids.length);
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
                'end_range': end_range
            },
            "success": function(data) {
                self.xform_history_cb(data);
            },
            "error": function(data) {
                console.log("Error");
                console.log(data);
            },
            "complete": function(data) {
                self.data_loading(false);
            }
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

