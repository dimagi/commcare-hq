$(function() {
    $(".button").button().wrap('<span />').addClass('shadow');
    $("input[type='submit']").button().addClass('shadow');
    $("input[type='text'], input[type='password'], textarea").addClass('shadow').addClass('ui-corner-all');

    $("#title-bar").addClass('container ui-corner-top');
    $('#main_container').addClass('ui-corner-all container shadow');
    $('.container').addClass('ui-widget ui-widget-content');

    // trick to give a select menu an initial value
    $('select[data-value]').each(function(){
        var val = $(this).attr('data-value');
        if(val) {
            $(this).find('option').removeAttr('selected');
            $(this).find('option[value="' + val + '"]').attr('selected', 'true');
        }
    });

});

// thanks to http://stackoverflow.com/questions/1149454/non-ajax-get-post-using-jquery-plugin
// thanks to http://stackoverflow.com/questions/1131630/javascript-jquery-param-inverse-function#1131658

(function($) {
    $.extend({
        getGo: function(url, params) {
            document.location = url + '?' + $.param(params);
        },
        postGo: function(url, params) {
            var $form = $("<form>")
                .attr("method", "post")
                .attr("action", url);
            $.each(params, function(name, value) {
                $("<input type='hidden'>")
                    .attr("name", name)
                    .attr("value", value)
                    .appendTo($form);
            });
            $form.appendTo("body");
            $form.submit();
        },
        unparam: function (value) {
            var
            // Object that holds names => values.
            params = {},
            // Get query string pieces (separated by &)
            pieces = value.split('&'),
            // Temporary variables used in loop.
            pair, i, l;

            // Loop through query string pieces and assign params.
            for (i = 0, l = pieces.length; i < l; i++) {
                pair = pieces[i].split('=', 2);
                // Repeated parameters with the same name are overwritten. Parameters
                // with no value get set to boolean true.
                params[decodeURIComponent(pair[0])] = (pair.length == 2 ?
                    decodeURIComponent(pair[1].replace(/\+/g, ' ')) : true);
            }

            return params;
        }
    });
})(jQuery);