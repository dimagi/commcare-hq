hqDefine('hqadmin/js/system_info', [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/alert_user',
], function (
    $,
    ko,
    _,
    initialPageData,
    alertUser
) {
    function format_date(datestring) {
        //parse and format the date timestamps - seconds since epoch into date object
        var date = new Date(datestring * 1000);
        // hours part from the timestamp
        var hours = date.getHours();
        // minutes part from the timestamp
        var minutes = date.getMinutes();
        // seconds part from the timestamp
        var seconds = date.getSeconds();
        if (seconds < 10) {
            var second_str = "0"+ seconds;
        } else {
            var second_str = seconds;
        }
    
        var year = date.getFullYear();
        var month = date.getMonth() + 1;
        var day = date.getDate();
    
        return  year + '/' + month + '/' + day + ' ' + hours + ':' + minutes + ':' +  second_str;
    
    }
    
    function number_fix(num) {
        if (num !== null) {
            if (num.toFixed) {
                return num.toFixed(2);
            }
            if (num.toPrecision) {
                return num.toPrecision(2);
            }
            return num;
        }
    }
    
    function RefreshableViewModel(url, model, interval, sort_by) {
        var self = this;
        self.error = ko.observable();
        self.models = ko.observableArray();
        self.autoRefresh = ko.observable(false);
        self.loading = ko.observable(false);
        self.timer = null;
        self.interval = interval;
    
        self.autoRefresh.subscribe(function (newVal) {
            if (newVal) {
                self.refresh();
            } else {
                self.clearTimer();
            }
        });
    
        self.clearTimer = function () {
            if (self.timer) {
                clearTimeout(self.timer);
                self.timer = null;
            }
        };
    
        self.refresh = function () {
            self.clearTimer();
            self.loading(true);
            $.getJSON(url, function (data) {
                self.error(null);
                var objects = _(data).map(function (item) {
                    return new model(item);
                });
                if (sort_by) {
                    objects = _(objects).sortBy(function (x) { return x[sort_by]; });
                }
                self.models(objects);
                if (self.autoRefresh()) {
                    self.timer = setTimeout(self.refresh, self.interval);
                }
            })
                .fail(function (jqxhr, textStatus, error) {
                    var err = 'Unknown server error';
                    try {
                        err = JSON.parse(jqxhr.responseText).error;
                    } catch (e) {}
                    self.error("Error: " + err);
                    self.autoRefresh(false);
                    self.timer = null;
                })
                .always(function (){
                    self.loading(false);
                });
        };
    }
    
    function ActiveTaskModel(data) {
    
        this.pid = ko.observable(data.pid);
        this.type = ko.observable(data.type);
        this.database = ko.observable(data.database);
        this.progress = ko.observable(data.progress + "%");
        this.design_document = ko.observable(data.design_document);
        this.started_on = ko.observable(format_date(data.started_on));
        this.updated_on = ko.observable(format_date(data.updated_on));
        this.total_changes = ko.observable(data.total_changes);
        this.changes_done = ko.observable(data.changes_done);
        this.progress_contribution = ko.observable(data.progress_contribution);
    }
    
    function DesignDocModel(data) {
        var self = this;
        self.design_document = ko.observable(data.design_document);
        self.details_id = self.design_document() + '_details';
        var tasks = _(data.tasks).map(function (task) {
            return new ActiveTaskModel(task);
        });
        self.tasks = ko.observableArray(tasks);
    
        self.showDetails = function () {
            $('#' + self.details_id).toggle();
        };
    }
    
    function CeleryTaskModel(data) {
        var self = this;
        this.name = ko.observable(data.name);
        this.uuid = ko.observable(data.uuid);
        this.state = ko.observable(data.state);
        this.received = ko.observable(format_date(data.received));
        this.started = ko.observable(format_date(data.started));
        this.timestamp = ko.observable(format_date(data.timestamp));
        this.succeeded = ko.observable(format_date(data.succeeded));
        this.retries = ko.observable(data.retries);
        this.args = ko.observable(data.args);
        this.kwargs = ko.observable(data.kwargs);
        this.runtime = ko.observable(number_fix(data.runtime));
    
        this.toggleArgs = function () {
            $('#' + self.uuid()).toggle();
        };
    }
    
    function PillowOperationViewModel(pillow_model, operation) {
        var self = this;
        self.pillow_model = pillow_model;
        self.operation = operation;
        self.title = operation + ' for ' + pillow_model.name();
    
        self.go = function () {
            self.pillow_model.perform_operation(operation);
        };
    }

    function PillowProgress(name, db_offset, seq) {
        var self = this;
        self.name = name;
        self.db_offset = db_offset;
        self.seq = seq;

        self.changes_behind = function () {
            return self.db_offset - self.seq;
        };

        self.width = function() {
            return (self.seq * 100) / self.db_offset;
        };
    
        self.status = function() {
            if (self.changes_behind() < 500) {
                return 'progress-bar-success';
            } else if (self.changes_behind() < 1000) {
                return ''; // will be a blue, but not quite info
            } else if (self.changes_behind() < 5000) {
                return 'progress-bar-warning';
            } else {
                return 'progress-bar-danger';
            }
        };
    }

    function PillowModel(pillow) {
        var self = this;
        self.name = ko.observable();
        self.seq_format = ko.observable();
        self.seq = ko.observable();
        self.offsets = ko.observable();
        self.time_since_last = ko.observable();
        self.show_supervisor_info = ko.observable();
        self.supervisor_state = ko.observable();
        self.supervisor_message = ko.observable();
        self.operation_in_progress = ko.observable(false);
        self.progress = ko.observableArray();
    
        self.update = function (data) {
            self.name(data.name);
            self.seq_format(data.seq_format);
            self.seq(data.seq);
            self.offsets(data.offsets);
            self.time_since_last(data.time_since_last);
            self.show_supervisor_info(!!data.supervisor_state);
            self.supervisor_state(data.supervisor_state||'(unavailable)');
            self.supervisor_message(data.supervisor_message);
    
            self.progress([]);
            if (self.seq_format() === 'json') {
                _.each(self.offsets(), function(db_offset, key) {
                    var value;
                    if (self.seq() === null || !self.seq().hasOwnProperty(key)) {
                        value = 0;
                    } else {
                        value = self.seq()[key];
                    }
                    self.progress.push(new PillowProgress(key, db_offset, value));
                });
            } else {
                var key = _.keys(self.offsets())[0];
                self.progress.push(new PillowProgress(key, self.offsets()[key], self.seq()));
            }
        };
    
        self.update(pillow);
    
        self.process_running = ko.computed(function () {
            return self.supervisor_state() === 'RUNNING';
        });
    
        self.start_stop_text = ko.computed(function () {
            return self.process_running() ? gettext("Stop") : gettext("Start");
        });
    
        self.disabled = ko.computed(function() {
            return self.operation_in_progress() || (self.supervisor_state() !== 'RUNNING' && self.supervisor_state() !== 'STOPPED');
        });
    
        self.supervisor_state_css = ko.computed(function() {
            switch (self.supervisor_state()) {
                case ('(unavailable)'):
                    return '';
                case ('RUNNING'):
                    return 'label-success';
                case ('STOPPED'):
                    return 'label-warning';
                default:
                    return 'label-danger';
            }
        });
    
        self.checkpoint_status_css = ko.computed(function() {
            var hours = pillow.hours_since_last;
            switch (true) {
                case (hours <= 1):
                    return 'label-success';
                case (hours <= 6):
                    return 'label-info';
                case (hours <= 12):
                    return 'label-warning';
                default:
                    return 'label-danger';
            }
        });
    
        self.overall_status = ko.computed(function() {
            var status_combined = self.checkpoint_status_css() + self.supervisor_state_css();
            if (status_combined.indexOf('important') !== -1) {
                return 'error';
            } else if (status_combined.indexOf('warning') !== -1) {
                return 'warning';
            } else if (status_combined.indexOf('info') !== -1) {
                return 'info';
            } else if (status_combined.indexOf('success') !== -1) {
                return 'success';
            }
        });
    
        self.show_pillow_dialog = function (operation) {
            var element = $('#pillow_operation_modal').get(0);
            ko.cleanNode(element);
            $(element).koApplyBindings(new PillowOperationViewModel(self, operation));
            $('#pillow_operation_modal').modal({
                backdrop: 'static',
                keyboard: false,
                show: true,
            });
        };
    
        self.reset_checkpoint = function () {
            self.show_pillow_dialog('reset_checkpoint');
        };
    
        self.start_stop = function () {
            self.show_pillow_dialog(self.process_running() ? 'stop' : 'start');
        };
    
        self.refresh = function () {
            self.perform_operation('refresh');
        };
    
        self.perform_operation = function(operation) {
            self.operation_in_progress(true);
            $.post(initialPageData.reverse("pillow_operation_api"), {
                'pillow_name': self.name,
                'operation': operation,
            }, function( data ) {
                self.operation_in_progress(false);
                self.update(data);
    
                if (!data.success) {
                    alertUser.alert_user("Operation failed: " + data.operation + " on "
                            + data.pillow_name + ', ' + data.message, 'danger');
                }
            }, "json")
                .fail(function (jqxhr, textStatus, error) {
                    var err = 'Unknown server error';
                    try {
                        err = JSON.parse(jqxhr.responseText).error;
                    } catch (e) {}
                    self.operation_in_progress(false);
                    self.supervisor_state('(unavailable)');
                    self.supervisor_message(err);
                }).always(function() {
                    $('#pillow_operation_modal').modal('hide');
                    $("#" + self.name() +" td").fadeTo( "fast" , 0.5).fadeTo( "fast" , 1);
                });
        };
    }
    
    function DbComparisons(data) {
        var self = this;
        self.description = data.description;
        self.es_docs = data.es_docs;
        self.couch_docs = data.couch_docs;
        self.sql_rows = data.sql_rows;
    }
    
    $(function () {
        var celery_update = initialPageData.get("celery_update"),
            couch_update = initialPageData.get("couch_update"),
            system_ajax_url = initialPageData.reverse("system_ajax");
        var celeryViewModel = new RefreshableViewModel(system_ajax_url + "?api=flower_poll", CeleryTaskModel, celery_update);
        var couchViewModel;
        if (initialPageData.get("is_bigcouch")) {
            var couchViewModel = new RefreshableViewModel(system_ajax_url + "?api=_active_tasks", DesignDocModel, couch_update, 'design_document');
        } else {
            var couchViewModel = new RefreshableViewModel(system_ajax_url + "?api=_active_tasks", ActiveTaskModel, couch_update);
        }
        var pillowtopViewModel = new RefreshableViewModel(system_ajax_url + "?api=pillowtop", PillowModel, couch_update, 'name');
    
        var AutoRefreshModel = function () {
            var self = this;
            self.refreshStatus = ko.observable(false);
            self.refreshStatusText = ko.observable('off');
            self.models = [];
    
            self.addModel = function (model) {
                self.models.push(model);
            };
    
            self.toggleRefresh = function () {
                self.refreshStatus(!self.refreshStatus());
                self.refreshStatusText(self.refreshStatus() ? 'on' : 'off');
                $.each(self.models, function (index, model) {
                    model.autoRefresh(self.refreshStatus());
                });
            };
    
            self.refreshAll = function () {
                $.each(self.models, function (index, model) {
                    model.refresh();
                });
            };
        };
    
        var autoRefresh = new AutoRefreshModel();
        $("#celeryblock").koApplyBindings(celeryViewModel);
        $("#couchblock").koApplyBindings(couchViewModel);
        $('#pillowtop-status').koApplyBindings(pillowtopViewModel);
        autoRefresh.addModel(celeryViewModel);
        autoRefresh.addModel(couchViewModel);
        autoRefresh.addModel(pillowtopViewModel);
    
        autoRefresh.refreshAll();
        $('#autorefresh').koApplyBindings(autoRefresh);
    });
});
