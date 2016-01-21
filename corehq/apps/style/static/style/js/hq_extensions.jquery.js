(function () {
    'use strict';
    $.extend({
        // thanks to http://stackoverflow.com/questions/1149454/non-ajax-get-post-using-jquery-plugin
        getGo: function (url, params) {
            document.location = url + '?' + $.param(params);
        },
        postGo: function (url, params) {
            params.csrfmiddlewaretoken = $.cookie('csrftoken');
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

    $.fn.closest_form = function () {
        return this.closest('form, .form');
    };

    $.fn.my_serialize = function () {
        var data = this.find('[name]').serialize();
        return data;
    };

    $.fn.addSpinnerToButton = function () {
        $(this).prepend('<i class="fa fa-refresh fa-spin icon-refresh icon-spin"></i> ');
    };

    $.fn.removeSpinnerFromButton = function () {
        $(this).find('i').remove();
    };

    $.fn.disableButtonNoSpinner = function () {
        $(this).attr('disabled', 'disabled')
            .addClass('disabled');
    };

    $.fn.disableButton = function () {
        $(this).disableButtonNoSpinner();
        $(this).addSpinnerToButton();
    };

    $.fn.enableButton = function () {
        $(this).removeSpinnerFromButton();
        $(this).removeClass('disabled')
            .removeAttr('disabled');
    };

    $.fn.koApplyBindings = function (context) {
        if (!this.length) {
            throw new Error("No element passed to koApplyBindings");
        }
        if (this.length > 1) {
            throw new Error("Multiple elements passed to koApplyBindings");
        }
        return ko.applyBindings(context, this.get(0));
    };
}());
