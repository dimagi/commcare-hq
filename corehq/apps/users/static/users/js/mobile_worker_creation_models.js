hqDefine("users/js/mobile_worker_creation_models", function() {
    var STATUS = {
        NEW: 'new',
        PENDING: 'pending',
        WARNING: 'warning',
        SUCCESS: 'success',
        RETRIED: 'retried',
    };

    var USERNAME_STATUS = {
        PENDING: 'pending',
        TAKEN: 'taken',
        AVAILABLE: 'available',
        AVAILABLE_WARNING: 'warning',
        ERROR: 'error',
    };

    var newMobileWorkerModel = function(options) {
        options = options || {};
        var self = hqImport("users/js/mobile_worker_models").mobileWorkerModel(options);

        self.usernameAvailabilityStatus = ko.observable('');
        self.usernameStatusMessage = ko.observable('');

        // TODO: translate messages
        // TODO: show messages styled
        // TODO: don't show messages when observable values are undefined
        // TODO: get username_max_length from ipd
        self.username.extend({
            required: true,
            maxLength: options.username_max_length || 10,
            validation: {
                async: true,
                validator: function (val, params, callback) {
                    if (self.username() && self.username.isValid()) {
                        self.usernameAvailabilityStatus(USERNAME_STATUS.PENDING);
                        self.usernameStatusMessage('');
                        // TODO: clear classes (visualFormCtrl.usernamePending in old code)
                        $.ajax({
                            method: 'GET',
                            url: hqImport("hqwebapp/js/initial_page_data").reverse('check_username'),
                            data: {
                                username: self.username(),
                            },
                            success: function(data) {
                                if (data.success) {
                                    // TODO: visualFormCtrl.usernameSuccess();
                                    self.usernameAvailabilityStatus(USERNAME_STATUS.AVAILABLE);
                                    self.usernameStatusMessage(data.success);
                                } else if (data.warning) {
                                    // TODO: visualFormCtrl.usernameWarning();
                                    self.usernameAvailabilityStatus(USERNAME_STATUS.AVAILABLE_WARNING);
                                    self.usernameStatusMessage(data.warning);
                                } else {
                                    // TODO: visualFormCtrl.usernameError();
                                    self.usernameAvailabilityStatus(USERNAME_STATUS.TAKEN);
                                    self.usernameStatusMessage(data.error);
                                }
                            },
                            error: function() {
                                self.usernameAvailabilityStatus(USERNAME_STATUS.ERROR);
                                self.usernameStatusMessage(gettext("Sorry, there was an issue communicating with the server."));
                            },
                        });
                    } else {
                        // TODO: clear classes (visualFormCtrl.usernameClear in old code)
                    }
                },
            },
        });
        self.first_name.extend({ maxLength: 30 });
        self.last_name.extend({ maxLength: 30 });
        self.password.extend({ required: { params: true, message: "custom message" } });
        self.isValid = ko.computed(function() {
            return self.username.isValid() && self.first_name.isValid() &&
                self.last_name.isValid() && self.password.isValid();
        });

        self.creationStatus = ko.observable('');
        self.isPending = ko.computed(function() { return self.creationStatus() === STATUS.PENDING; });
        self.isSuccess = ko.computed(function() { return self.creationStatus() === STATUS.SUCCESS; });
        self.isWarning = ko.computed(function() { return self.creationStatus() === STATUS.WARNING; });

        self.usernameIsPending = ko.computed(function() { return self.usernameAvailabilityStatus() === USERNAME_STATUS.PENDING; });
        self.usernameIsTaken = ko.computed(function() { return self.usernameAvailabilityStatus() === USERNAME_STATUS.TAKEN; });
        self.usernameIsAvailable = ko.computed(function() { return self.usernameAvailabilityStatus() === USERNAME_STATUS.AVAILABLE; });
        self.usernameIsWarning = ko.computed(function() { return self.usernameAvailabilityStatus() === USERNAME_STATUS.AVAILABLE_WARNING; });
        self.usernameIsError = ko.computed(function() { return self.usernameAvailabilityStatus() === USERNAME_STATUS.ERROR; });

        return self;
    };

    var newMobileWorkersListModel = function() {
        var self = {};

        self.users = ko.observableArray([]);
        self.hasUsers = ko.computed(function() {
            return self.users().length;
        });

        self.mobileWorker = newMobileWorkerModel();  // new worker being added
        self.mobileWorker.clear();
        self.initializeMobileWorker = function() {
            self.mobileWorker.clear();
            self.mobileWorker.usernameAvailabilityStatus('');
            hqImport('analytix/js/google').track.event('Manage Mobile Workers', 'New Mobile Worker', '');
        };

        self.allowMobileWorkerCreation = ko.computed(function() {
            return self.mobileWorker.isValid() && self.mobileWorker.usernameAvailabilityStatus() === USERNAME_STATUS.AVAILABLE;
        });

        self.submitNewMobileWorker = function() {
            $("#newMobileWorkerModal").modal('hide');
            var newWorker = _.clone(self.mobileWorker);
            self.users.push(newWorker);
            newWorker.creationStatus(STATUS.PENDING);

            var deferred = $.Deferred();
            // TODO
            /*if (typeof(hex_parser) !== 'undefined') {
                newWorker.password = (new hex_parser()).encode(newWorker.password);
            }*/

            $.ajax({
                method: 'POST',
                url: hqImport("hqwebapp/js/initial_page_data").reverse("create_mobile_worker"),
                data: {
                    username: newWorker.username(),
                    password: newWorker.password(),
                    customFields: JSON.stringify(newWorker.customFields),
                    first_name: newWorker.first_name(),
                    last_name: newWorker.first_name(),
                    location_id: newWorker.location_id(),
                },
                success: function(data) {
                    if (data.success) {
                        newWorker.creationStatus(STATUS.SUCCESS);
                        newWorker.editUrl(data.editUrl);    // TODO: test
                        deferred.resolve(data);
                    } else {
                        newWorker.creationStatus(STATUS.WARNING);
                        deferred.reject(data);
                    }
                },
                error: function(data) {
                    // TODO: test
                    newWorker.creationStatus(STATUS.WARNING);
                    deferred.reject(
                        gettext("Sorry, there was an issue communicating with the server.")
                    );
                },
            });
        };

        self.retryMobileWorker = function() {
            self.mobileWorker.usernameAvailabilityStatus(USERNAME_STATUS.AVAILABLE);
            self.mobileWorker.usernameStatusMessage(gettext('Username is available.'));
            console.log("do something");
        };

        return self;
    };

    return {
        newMobileWorkerModel: newMobileWorkerModel,
        newMobileWorkersListModel: newMobileWorkersListModel,
    }
});
