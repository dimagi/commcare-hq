$.prototype.iconify = function (icon) {
    'use strict';
    var $icon = $("<div/>").addClass('ui-icon ' + icon).css('float', 'left');
    $(this).css('width', "16px").prepend($icon);
};

var COMMCAREHQ = (function () {
    'use strict';
    return {
        initBlock: function ($elem) {
            $('.submit_on_click', $elem).click(function (e) {
                e.preventDefault();
                $(this).closest('form').submit();
            });
            // trick to give a select menu an initial value
            $('select[data-value]', $elem).each(function () {
                var val = $(this).attr('data-value');
                if (val) {
                    $(this).find('option').removeAttr('selected');
                    $(this).find('option[value="' + val + '"]').attr('selected', 'true');
                }
            });

            $(".button", $elem).button().wrap('<span />');
            $("input[type='submit']", $elem).button();
            $("input[type='text'], input[type='password'], textarea", $elem);//.addClass('shadow').addClass('ui-corner-all');
            $('.container', $elem).addClass('ui-widget ui-widget-content');
            $('.config', $elem).wrap('<div />').parent().addClass('container block ui-corner-all');

            $('.help-link', $elem).each(function () {
                var HELP_KEY_ATTR = "data-help-key",
                    $help_link = $(this),
                    help_key = $help_link.attr(HELP_KEY_ATTR),
                    $help_text = $('.help-text[' + HELP_KEY_ATTR + '="' + help_key + '"]');
                if (!$help_text.length) {
                    $help_text = $('<div class="help-text" />').insertAfter($help_link);
                }
                $help_text.addClass('shadow');
                new InlineHelp($help_link, $help_text, help_key).init();
            });
            $('.hidden').hide();
        },
        updateDOM: function (update) {
            var key;
            for (key in update) {
                if (update.hasOwnProperty(key)) {
                    $(key).text(update[key]);
                }
            }
        },
        confirm: function (options) {
            var title = options.title,
                message = options.message || "",
                onOpen = options.open || function () {},
                onOk = options.ok,
                $dialog = $('<div/>');

            if (typeof message === "function") {
                message.apply($dialog);
            } else if (message) {
                $dialog.text(message);
            }
            $dialog.dialog({
                    title: title,
                    modal: true,
                    resizable: false,
                    open: function () {
                        onOpen.apply($dialog);
                    },
                    buttons: [{
                        text: "Cancel",
                        click: function () {
                            $(this).dialog('close');
                        }
                    }, {
                        text: "OK",
                        click: function () {
                            $(this).dialog('close');
                            onOk.apply($dialog);
                        }
                    }]
                });
        }
    };
}());

function setUpIeWarning() {
    'use strict';
    var $warning;
    if ($.browser.msie) {
        $warning= $('<div/>').addClass('ie-warning');
        $('<span>This application does not work well on Microsoft Internet Explorer. ' +
          'Please use <a href="http://www.google.com/chrome/">Google Chrome</a> instead.</span>').appendTo($warning);
        $('body').prepend($warning);
    }
}

$(function () {
    'use strict';
    $('.hidden').hide();
    $('.delete_link').iconify('ui-icon-closethick');
    $(".delete_link").addClass("dialog_opener");
    $(".delete_dialog").addClass("dialog");
    $('.new_link').iconify('ui-icon-plusthick');
    $('.edit_link').iconify('ui-icon-pencil');
    var dragIcon = 'ui-icon-grip-dotted-horizontal';
    $('.drag_handle').iconify(dragIcon);

    $(".message").addClass('ui-state-highlight ui-corner-all').addClass("shadow");

    $('#main_container').addClass('ui-corner-all container shadow');


    $(".sidebar").addClass('ui-widget ui-widget-content ui-corner-bl');
    $(".sidebar h2").addClass('ui-corner-all');
    $(".sidebar ul li").addClass('ui-corner-all');
    $(".sidebar ul li div").addClass('ui-corner-top');
    $(".sidebar ul").addClass('ui-corner-bottom');

    COMMCAREHQ.initBlock($("body"));
    setUpIeWarning();
});

// thanks to http://stackoverflow.com/questions/1149454/non-ajax-get-post-using-jquery-plugin
// thanks to http://stackoverflow.com/questions/1131630/javascript-jquery-param-inverse-function#1131658

(function () {
    'use strict';
    $.extend({
        getGo: function (url, params) {
            document.location = url + '?' + $.param(params);
        },
        postGo: function (url, params) {
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
}());