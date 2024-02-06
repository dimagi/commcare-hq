hqDefine('sso/js/models', [
    'jquery',
    'knockout',
], function (
    $,
    ko
) {

    // todo make this into a better reusable component for HQ?

    var linkedObjectListModel = function (initial) {
        'use strict';
        var self = {};

        self.requestContext = initial.requestContext;

        self.asyncHandler = initial.asyncHandler;
        self.initAction = initial.initAction || 'get_linked_objects';
        self.addAction = initial.addAction || 'add_object';
        self.removeAction = initial.removeAction || 'remove_object';
        self.validateNewObjectFn = initial.validateNewObjectFn;

        self.linkedObjects = ko.observableArray();
        self.newObject = ko.observable('');
        self.hasFinishedInit = ko.observable(false);

        self.addObjectError = ko.observable();
        self.newObject.subscribe(function () {
            self.addObjectError('');
        });

        self.asyncHandlerError = ko.observable();

        self.isNewObjectValid = ko.computed(function () {
            return self.validateNewObjectFn(self.newObject());
        });
        self.isAddDisabled = ko.computed(function () {
            return !self.isNewObjectValid();
        });
        self.showNoObjectsMessage = ko.computed(function () {
            return self.linkedObjects().length === 0 && self.hasFinishedInit();
        });

        self.init = function () {
            $.post({
                url: '',
                data: {
                    handler: self.asyncHandler,
                    action: self.initAction,
                    requestContext: self.requestContext,
                },
                success: function (response) {
                    if (response.success) {
                        self.hasFinishedInit(true);
                        self.linkedObjects(response.data.linkedObjects);
                    } else {
                        self.asyncHandlerError(response.error);
                    }
                },
            });
        };

        self.addObject = function () {
            self.asyncHandlerError('');
            self.addObjectError('');
            if (self.isNewObjectValid()) {
                $.post({
                    url: '',
                    data: {
                        handler: self.asyncHandler,
                        action: self.addAction,
                        objectName: self.newObject(),
                        requestContext: self.requestContext,
                    },
                    success: function (response) {
                        if (response.success) {
                            self.newObject('');
                            self.linkedObjects(response.data.linkedObjects);
                        } else {
                            self.addObjectError(response.error);
                        }
                    },
                });
            }
        };

        self.removeObject = function (objectName) {
            self.asyncHandlerError('');
            $.post({
                url: '',
                data: {
                    handler: self.asyncHandler,
                    action: self.removeAction,
                    objectName: objectName,
                    requestContext: self.requestContext,
                },
                success: function (response) {
                    if (response.success) {
                        self.linkedObjects(response.data.linkedObjects);
                    } else {
                        self.asyncHandlerError(response.error);
                    }
                },
            });
        };

        return self;
    };

    return {
        linkedObjectListModel: linkedObjectListModel,
    };
});
