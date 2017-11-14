hqDefine("hqwebapp/js/hq_extensions.jquery", ["jquery"], function($) {
    'use strict';
    $.extend({
        postGo: function (url, params) {
            params.csrfmiddlewaretoken = $("#csrfTokenContainer").val();
            var $form = $("<form>")
                .attr("method", "post")
                .attr("action", url);
            $.each(params, function (name, value) {
                $("<input type='hidden'>")
                    .attr("name", name)
                    .attr("value", value)
                    .appendTo($form);
            });
            $form.appendTo("body");
            $form.submit();
        },
        // thanks to http://stackoverflow.com/questions/1131630/javascript-jquery-param-inverse-function#1131658
        unparam: function (value) {
            var
            // Object that holds names => values.
                params = {},
            // Get query string pieces (separated by &)
                pieces = value.split('&'),
            // Temporary variables used in loop.
                pair, i, l;

            // Loop through query string pieces and assign params.
            for (i = 0, l = pieces.length; i < l; i += 1) {
                pair = pieces[i].split('=', 2);
                // Repeated parameters with the same name are overwritten. Parameters
                // with no value get set to boolean true.
                params[decodeURIComponent(pair[0])] = (pair.length === 2 ?
                    decodeURIComponent(pair[1].replace(/\+/g, ' ')) : true);
            }

            return params;
        }
    });

    return 1;   // Flag the module as loaded by hqModules.js
});
