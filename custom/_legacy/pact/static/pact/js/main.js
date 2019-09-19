hqDefine("pact/js/main", function () {
    var initialPageData = hqImport("hqwebapp/js/initial_page_data");

    function format_date(isodatestring) {
        if (isodatestring == "" || isodatestring == null) {
          return 'present';
        }
        //parse nad format the date timestamps - seconds since epoch into date object
        var date = new Date(isodatestring);
        // hours part from the timestamp
        var hours = date.getHours();
        // minutes part from the timestamp
        var minutes = date.getMinutes();
        // seconds part from the timestamp
        var seconds = date.getSeconds();
        if (seconds < 10) {
          var second_str = "0" + seconds;
        } else {
          var second_str = seconds;
        }

        var year = date.getFullYear();
        var month = date.getMonth() + 1;
        var day = date.getDate();

        return  month + '/' + day + '/' + year;
    }

    function format_user(username) {
        if (username === undefined) {
            return "---"
        }
        if (username == "" || username == null ) {
            return "---"
        }
        else {
            return username;
        }
    }

    function ScheduleModel(data) {
        this.schedule_id = ko.observable(data.schedule_id);
        this.sunday = ko.observable(format_user(data.sunday));
        this.monday = ko.observable(format_user(data.monday));
        this.tuesday = ko.observable(format_user(data.tuesday));
        this.wednesday = ko.observable(format_user(data.wednesday));
        this.thursday = ko.observable(format_user(data.thursday));
        this.friday = ko.observable(format_user(data.friday));
        this.saturday = ko.observable(format_user(data.saturday));
        this.comment = ko.observable(data.comment);

        this.created_by = ko.observable(data.created_by);
        this.edited_by = ko.observable(data.edited_by);
        this.started = ko.observable(data.started);
        this.ended = ko.observable(data.ended);

        this.display_started = ko.observable(format_date(data.started));
        this.display_ended = ko.observable(format_date(data.ended));

        this.deprecated = ko.observable(data.deprecated);
    }

    function ScheduleListViewModel() {
        var self = this;
        self.getSchedules = function () {
            var api_url = initialPageData.reverse('pactdata_1') + "?case_id=" + initialPageData.get('patient_id');
            $.getJSON(api_url + "&method=schedule", function (allData) {
                var mappedSchedules = $.map(allData, function (item) {
                    return new ScheduleModel(item)
                });
                self.schedules(mappedSchedules);
              }
            );
        };
        self.schedules = ko.observableArray(self.getSchedules());

        self.refresh = function () {
            self.getSchedules();
        };

        self.removeLast = function() {
            var api_url = initialPageData.reverse('pactdata_1') + "?case_id=" + initialPageData.get('patient_id');
            var json_schedules = ko.toJSON(self.schedules);
            if (confirm("This will immediately remove this data. Are you sure you wish to do so?")) {
                $.ajax({
                    "type": "POST",
                    "url":  api_url + "&method=rm_schedule",
                    "data": {"rm_schedule":""},
                    "success": function(data) {
                        scheduleView.refresh();
                    },
                    "error": function(data) {
                        alert ("Error trying to save form, please try again.");
                    }
                });
            }
        };

        self.currentSchedule = function(idx) {
            return idx == self.schedules().length -1;
        }
    }

    function ProviderModel(data) {
        this.id = ko.observable(data.id);
        this.first_name = ko.observable(data.first_name);
        this.last_name = ko.observable(data.last_name);
        this.email = ko.observable(data.email);
        this.role = ko.observable(data.role);

        this.facility_name = ko.observable(data.facility_name);
        this.facility_address = ko.observable(data.facility_address);
    }

    function ProviderListViewModel() {
        var self = this;
        self.is_loading = ko.observable(false);
        self.selectedFacility = ko.observable("All Facilities");
        self.providers = ko.observableArray([]);
        self.facilities = ko.observableArray([]);
        self.original = ko.observableArray([]);
        self.showSave = ko.observable(false);
        self.selected_providers = ko.observableArray([]);

        var api_url = initialPageData.reverse('pactdata_1') + "?case_id=" + initialPageData.get('patient_id');
        $.getJSON(api_url + "&method=providers", function (providerData) {
            console.log(providerData);

            var mappedSelected = $.map(providerData['case_providers'], function (item) {
                return new ProviderModel(item);
            });
            self.selected_providers(mappedSelected);

            var originalSelected = $.map(providerData['case_providers'], function (item) {
                return new ProviderModel(item);
            });

            self.original(originalSelected);

            var mappedProviders = $.map(providerData['providers'], function (item) {
                return new ProviderModel(item);
            });
            self.providers(mappedProviders);
            self.facilities(providerData['facilities']);
        });

        self.inSelectedProviders = function(item) {
            //sanity check to see if it's in the active list, this does a scan though, nasty
            for (var i = 0; i < self.selected_providers().length; i++) {
                if (item.id() == self.selected_providers()[i].id()) {
                    return true;
                }
            }
            return false;
        };

        self.providerUp = function(item) {
            var idx = self.selected_providers().indexOf(item);
            var up = idx - 1;
            var arr = self.selected_providers();
            var up_item = self.selected_providers()[up];

            arr[up] = item;
            arr[idx] = up_item;
            self.selected_providers(arr);
        };

        self.providerDown = function(item) {
            var idx = self.selected_providers().indexOf(item);
            var down = idx + 1;
            var arr = self.selected_providers();

            var up_item = self.selected_providers()[down];
            arr[down] = item;
            arr[idx] = up_item;
            self.selected_providers(arr);
        };

        self.showInAvailableProviders = function(item) {
            if (self.inSelectedProviders(item)) {
                return false;
            }

            var facility = self.selectedFacility();
            if (facility === undefined) {
                return true;
            } else if (facility === 'All Facilities') {
                return true;
            }

            if (facility != item.facility_name()) {
                return false;
            } else if (facility === item.facility_name()) {
                return true;
            }
        };

        self.providersChanged = self.selected_providers.subscribe(function (data) {
            self.showSave(true);
        });

        self.addProvider = function(provider) {
            if (self.selected_providers().length >= 9) {
              alert("Sorry, the limit for providers is 9");
              return;
            }
            self.selected_providers.push(provider);
            var idx = self.providers().indexOf(provider);
            var arr = self.providers();
            arr.splice(idx, 1);
            self.providers(arr);
        };

        self.rmProvider = function(provider) {
            self.providers.push(provider);
            var idx = self.selected_providers().indexOf(provider);
            var arr = self.selected_providers();
            arr.splice(idx, 1);
            self.selected_providers(arr);
        };

        function csrfSafeMethod(method) {
            // these HTTP methods do not require CSRF protection
            return (/^(GET|HEAD|OPTIONS|TRACE)$/.test(method));
        }

        self.saveProviders = function() {
            self.is_loading(true);
            self.showSave(false);
            var arr = self.selected_providers();
            var csrftoken = $("#csrfTokenContainer").val();

            var provider_ids = $.map(arr, function (item) {
              return item.id();
            });
            console.log(provider_ids);

            $.ajaxSetup({
                crossDomain: false, // obviates need for sameOrigin test
                beforeSend: function(xhr, settings) {
                    if (!csrfSafeMethod(settings.type)) {
                        xhr.setRequestHeader("X-CSRFToken", csrftoken);
                    }
                }
            });

            var api_url = initialPageData.reverse('pactdata_1') + "?case_id=" + initialPageData.get('patient_id');
            $.ajax({
                "type": "POST",
                "url":  api_url + "&method=providers",
                "data": {selected_providers: ko.toJSON(provider_ids) },
                "success": function(data) {
                    console.log(data);
                },
                "error": function(data) {
                    console.log(data);
                },
                "complete": function(data){
                    self.is_loading(false);
                    self.showSave(true);
                }
            });
        }
    }

    $(function () {
        // Widget initialization
        $("#tbl_issues").tablesorter();
        $("abbr.timeago").timeago();
        $(".timeago").timeago();

        // Edit page
        $("#submit_button").click(function() {
            var form_data = $("#pt_edit_form").serialize();
            var api_url = initialPageData.reverse('pactdata_1') + "?case_id=" + initialPageData.get('patient_id') + "&method=patient_edit";
            console.log(form_data);
            $.ajax({
                "type": "POST",
                "url":  api_url,
                "data": form_data,
                "success": function(data) {
                    window.location.href = initialPageData.get('pt_root_url') + "&view=info";
                },
                "error": function(data) {
                    if(data.responseText !== undefined) {
                        $("#form_errors").html(data.responseText);
                    }
                }
            });
        });

        // Providers page
        var providerView = new ProviderListViewModel();
        $("#providerblock").koApplyBindings(providerView);

        // Schedule page
        var scheduleView = new ScheduleListViewModel();
        $("#scheduleblock").koApplyBindings(scheduleView);
        $("#id_active_date").datepicker({ minDate: 0, maxDate: "+14D" });
        $('#new_schedule_form').ajaxForm(function() {
            var api_url = initialPageData.reverse('pactdata_1') + "?case_id=" + initialPageData.get('patient_id');
            var send_xhr = $.ajax({
                "type": "POST",
                "url":  api_url + "&method=schedule",
                "data": $("#new_schedule_form").serialize(),
                "success": function(data) {
                    console.log(data);
                    scheduleView.refresh();
                },
                "error": function(data) {
                    console.log(data);
                    alert ("Error trying to save form, please try again.");
                }
            });
        });
    });
});
