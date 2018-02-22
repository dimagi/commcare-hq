/* globals $ */
/* globals window */

hqDefine('app_manager/js/forms/edit_form_details', function () {
    'use strict';
    var module = {};

    module.name = ko.observable();
    module.comment = ko.observable();
    
    var _updateCallbackFn = function (name, comment) {};

    module.initName = function (name, url) {
        module.name(name);
        module.updateNameUrl = url;
    };
    
    module.initComment = function (comment, url) {  
        module.comment(comment);
        module.updateCommentUrl = url;
    };
    
    module.setUpdateCallbackFn = function (callbackFn) {
        _updateCallbackFn = callbackFn;
    };

    module.update = function () {
        $.ajax({
            url: module.updateNameUrl,
            type: 'POST',
            dataType: 'JSON',
            data: { name: module.name() },
            success: function (data){
                $.ajax({
                    url: module.updateCommentUrl,
                    type: 'POST',
                    dataType: 'JSON',
                    data: { comment: module.comment() },
                    success: function (data){
                        _updateCallbackFn(module.name(), module.comment());
                    },
                });
            },
        });
    };

    return module;
});
