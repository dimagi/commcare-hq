hqDefine('hqadmin/js/system_info', [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/bootstrap3/alert_user',
], function (
    $,
    ko,
    _,
    initialPageData,
    alertUser
) {
    function formatDate(datestring) {
        //parse and format the date timestamps - seconds since epoch into date object
        var date = new Date(datestring * 1000);
        // hours part from the timestamp
        var hours = date.getHours();
        // minutes part from the timestamp
        var minutes = date.getMinutes();
        // seconds part from the timestamp
        var seconds = date.getSeconds(),
            secondStr;
        if (seconds < 10) {
            secondStr = "0" + seconds;
        } else {
            secondStr = seconds;
        }

        var year = date.getFullYear();
        var month = date.getMonth() + 1;
        var day = date.getDate();

        return  year + '/' + month + '/' + day + ' ' + hours + ':' + minutes + ':' +  secondStr;

    }

    function numberFix(num) {
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

    function refreshableViewModel(url, model, interval, sortBy) {
        var self = {};
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
                if (sortBy) {
                    objects = _(objects).sortBy(function (x) { return x[sortBy]; });
                }
                self.models(objects);
                if (self.autoRefresh()) {
                    self.timer = setTimeout(self.refresh, self.interval);
                }
            })
                .fail(function (jqxhr) {
                    var err = 'Unknown server error';
                    /* eslint-disable no-empty */
                    try {
                        err = JSON.parse(jqxhr.responseText).error;
                    } catch (e) {
                        // this is fine
                    }
                    /* eslint-enable no-empty */
                    self.error("Error: " + err);
                    self.autoRefresh(false);
                    self.timer = null;
                })
                .always(function () {
                    self.loading(false);
                });
        };

        return self;
    }

    function activeTaskModel(data) {
        var self = {};
        self.pid = ko.observable(data.pid);
        self.type = ko.observable(data.type);
        self.database = ko.observable(data.database);
        self.progress = ko.observable(data.progress + "%");
        self.designDocument = ko.observable(data.design_document);
        self.startedOn = ko.observable(formatDate(data.started_on));
        self.updatedOn = ko.observable(formatDate(data.updated_on));
        self.totalChanges = ko.observable(data.total_changes);
        self.changesDone = ko.observable(data.changes_done);
        self.progressContribution = ko.observable(data.progress_contribution);
        return self;
    }

    function designDocModel(data) {
        var self = {};
        self.designDocument = ko.observable(data.design_document);
        self.detailsId = self.design_document() + '_details';
        var tasks = _(data.tasks).map(function (task) {
            return activeTaskModel(task);
        });
        self.tasks = ko.observableArray(tasks);

        self.showDetails = function () {
            $('#' + self.detailsId).toggle();
        };
        return self;
    }

    function celeryTaskModel(data) {
        var self = {};
        this.name = ko.observable(data.name);
        this.uuid = ko.observable(data.uuid);
        this.state = ko.observable(data.state);
        this.received = ko.observable(formatDate(data.received));
        this.started = ko.observable(formatDate(data.started));
        this.timestamp = ko.observable(formatDate(data.timestamp));
        this.succeeded = ko.observable(formatDate(data.succeeded));
        this.retries = ko.observable(data.retries);
        this.args = ko.observable(data.args);
        this.kwargs = ko.observable(data.kwargs);
        this.runtime = ko.observable(numberFix(data.runtime));

        this.toggleArgs = function () {
            $('#' + self.uuid()).toggle();
        };
        return self;
    }

    function pillowOperationViewModel(pillowModel, operation) {
        var self = {};
        self.pillowModel = pillowModel;
        self.operation = operation;
        self.title = operation + ' for ' + pillowModel.name();

        self.go = function () {
            self.pillowModel.performOperation(operation);
        };
        return self;
    }

    function pillowProgress(name, dbOffset, seq) {
        var self = {};
        self.name = name;
        self.dbOffset = dbOffset;
        self.seq = seq;

        self.changesBehind = function () {
            return self.dbOffset - self.seq;
        };

        self.width = function () {
            return (self.seq * 100) / self.dbOffset;
        };

        self.status = function () {
            if (self.changesBehind() < 500) {
                return 'progress-bar-success';
            } else if (self.changesBehind() < 1000) {
                return ''; // will be a blue, but not quite info
            } else if (self.changesBehind() < 5000) {
                return 'progress-bar-warning';
            } else {
                return 'progress-bar-danger';
            }
        };
        return self;
    }

    function pillowModel(pillow) {
        var self = {};
        self.name = ko.observable();
        self.seq_format = ko.observable();
        self.seq = ko.observable();
        self.offsets = ko.observable();
        self.timeSinceLast = ko.observable();
        self.operationInProgress = ko.observable(false);
        self.progress = ko.observableArray();

        self.update = function (data) {
            self.name(data.name);
            self.seq_format(data.seq_format);
            self.seq(data.seq);
            self.offsets(data.offsets);
            self.timeSinceLast(data.timeSinceLast);

            self.progress([]);
            if (self.seq_format() === 'json') {
                _.each(self.offsets(), function (dbOffset, key) {
                    var value;
                    if (self.seq() === null || !self.seq().hasOwnProperty(key)) {
                        value = 0;
                    } else {
                        value = self.seq()[key];
                    }
                    self.progress.push(pillowProgress(key, dbOffset, value));
                });
            } else {
                var key = _.keys(self.offsets())[0];
                self.progress.push(pillowProgress(key, self.offsets()[key], self.seq()));
            }
        };

        self.update(pillow);

        self.checkpointStatusCss = ko.computed(function () {
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

        self.overallStatus = ko.computed(function () {
            var statusCombined = self.checkpointStatusCss();
            if (statusCombined.indexOf('important') !== -1) {
                return 'error';
            } else if (statusCombined.indexOf('warning') !== -1) {
                return 'warning';
            } else if (statusCombined.indexOf('info') !== -1) {
                return 'info';
            } else if (statusCombined.indexOf('success') !== -1) {
                return 'success';
            }
        });

        self.showPillowDialog = function (operation) {
            var element = $('#pillow_operation_modal').get(0);
            ko.cleanNode(element);
            $(element).koApplyBindings(pillowOperationViewModel(self, operation));
            $('#pillow_operation_modal').modal({
                backdrop: 'static',
                keyboard: false,
                show: true,
            });
        };

        self.refresh = function () {
            self.performOperation('refresh');
        };

        self.performOperation = function (operation) {
            self.operationInProgress(true);
            $.post(initialPageData.reverse("pillow_operation_api"), {
                'pillow_name': self.name,
                'operation': operation,
            }, function (data) {
                self.operationInProgress(false);
                self.update(data);

                if (!data.success) {
                    alertUser.alert_user("Operation failed: " + data.operation + " on "
                            + data.pillow_name + ', ' + data.message, 'danger');
                }
            }, "json")
                .fail(function (jqxhr) {
                    var err = 'Unknown server error';
                    try {
                        err = JSON.parse(jqxhr.responseText).error;
                    } catch (e) {
                        // do nothing
                    }
                    self.operationInProgress(false);
                }).always(function () {
                    $('#pillow_operation_modal').modal('hide');
                    $("#" + self.name() + " td").fadeTo("fast" , 0.5).fadeTo("fast" , 1);
                });
        };

        return self;
    }

    $(function () {
        var celeryUpdate = initialPageData.get("celery_update"),
            couchUpdate = initialPageData.get("couch_update"),
            systemAjaxUrl = initialPageData.reverse("system_ajax");
        var celeryViewModel = refreshableViewModel(systemAjaxUrl + "?api=flower_poll", celeryTaskModel, celeryUpdate);
        var couchViewModel;
        if (initialPageData.get("is_bigcouch")) {
            couchViewModel = refreshableViewModel(systemAjaxUrl + "?api=_active_tasks", designDocModel, couchUpdate, 'designDocument');
        } else {
            couchViewModel = refreshableViewModel(systemAjaxUrl + "?api=_active_tasks", activeTaskModel, couchUpdate);
        }
        var pillowtopViewModel = refreshableViewModel(systemAjaxUrl + "?api=pillowtop", pillowModel, couchUpdate, 'name');

        var autoRefreshModel = function () {
            var self = {};
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

            return self;
        };

        var autoRefresh = autoRefreshModel();
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
