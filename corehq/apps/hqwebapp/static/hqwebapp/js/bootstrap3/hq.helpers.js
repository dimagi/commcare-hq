import $ from "jquery";
import ko from "knockout";
import _ from "underscore";
import googleAnalytics from "analytix/js/google";
import "bootstrap";  // for popover constructor override
import "jquery.cookie/jquery.cookie";  // $.cookie

// disable-on-submit is a class for form submit buttons so they're automatically disabled when the form is submitted
$(document).on('submit', 'form', function (ev) {
    var form = $(ev.target);
    form.find('.disable-on-submit').disableButton();
    form.find('.disable-on-submit-no-spinner').disableButtonNoSpinner();
});
$(document).on('submit', 'form.disable-on-submit', function (ev) {
    $(ev.target).find('[type="submit"]').disableButton();
});
$(document).on('reset', 'form', function (ev) {
    $(ev.target).find('.disable-on-submit').enableButton();
});
$(document).on('reset', 'form.disable-on-submit', function (ev) {
    $(ev.target).enableButton();
});
$(document).on('click', '.add-spinner-on-click', function (ev) {
    $(ev.target).addSpinnerToButton();
});

$(document).on('click', '.notification-close-btn', function () {
    var noteId = $(this).data('note-id');
    var postUrl = $(this).data('url');
    $.post(postUrl, {note_id: noteId});
    $(this).parents('.alert').hide(150);
});

window.onerror = function (message, file, line, col, error) {
    var stack = error ? error.stack : null;
    if (!stack && (
        message === 'Script error'
        || message === 'Script error.'
        || message === 'ResizeObserver loop limit exceeded'
    )) {
        return false;
    }
    $.post('/jserror/', {
        message: message,
        page: window.location.href,
        file: file,
        line: line,
        stack: stack,
    });
    return false; // let default handler run
};

var oldHide = $.fn.popover.Constructor.prototype.hide;

$.fn.popover.Constructor.prototype.hide = function () {
    if (this.options.trigger === "hover" && this.tip().is(":hover")) {
        var that = this;
        setTimeout(function () {
            return that.hide.apply(that, arguments);
        }, that.options.delay.hide);
        return;
    }
    oldHide.apply(this, arguments);
};

$.fn.hqHelp = function (opts) {
    var self = this;
    self.each(function (i) {
        var $self = $(self),
            $helpElem = $($self.get(i)),
            $link = $helpElem.find('a');

        var options = {
            html: true,
            trigger: 'focus',
            container: 'body',
            sanitize: false,
        };
        if (opts) {
            options = _.extend(options, opts);
        }
        if (!$link.data('content')) {
            options.content = function () {
                return $('#popover_content_wrapper').html();
            };
        }
        if (!$link.data("title")) {
            options.template = '<div class="popover"><div class="arrow"></div><div class="popover-inner"><div class="popover-content"><p></p></div></div></div>';
        }
        $link.popover(options);

        // Prevent jumping to the top of the page when link is clicked
        $helpElem.find('a').click(function (event) {
            googleAnalytics.track.event("Clicked Help Bubble", $(this).data('title'), '-');
            event.preventDefault();
        });
    });
};

$.fn.addSpinnerToButton = function () {
    $(this).find("i").addClass("hide");
    $(this).prepend('<i class="fa fa-refresh fa-spin icon-refresh icon-spin"></i> ');
};


$.fn.removeSpinnerFromButton = function () {
    $(this).find("i.hide").removeClass("hide");
    $(this).find('i.fa-spin').remove();
};


$.fn.disableButtonNoSpinner = function () {
    $(this).prop('disabled', 'disabled')
        .addClass('disabled');
};


$.fn.disableButton = function () {
    $(this).disableButtonNoSpinner();
    $(this).addSpinnerToButton();
};


$.fn.enableButton = function () {
    $(this).removeSpinnerFromButton();
    $(this).removeClass('disabled')
        .prop('disabled', false);
};

$.fn.koApplyBindings = function (context) {
    if (!this.length) {
        throw new Error("No element passed to koApplyBindings");
    }
    if (this.length > 1) {
        throw new Error("Multiple elements passed to koApplyBindings");
    }
    ko.applyBindings(context, this.get(0));
    this.find('.ko-template').addBack().removeClass('ko-template');
};

$.ajaxSetup({
    beforeSend: function (xhr, settings) {
        // Don't pass csrftoken cross domain
        // Ignore HTTP methods that do not require CSRF protection
        if (!/^(GET|HEAD|OPTIONS|TRACE)$/.test(settings.type)) {
            if (!this.crossDomain) {
                var csrfToken = $("#csrfTokenContainer").val();
                if (csrfToken) {
                    xhr.setRequestHeader("X-CSRFToken", csrfToken);
                }
            }
            var xsrfToken = $.cookie('XSRF-TOKEN');
            if (xsrfToken) {
                xhr.setRequestHeader('X-XSRF-TOKEN', xsrfToken);
            }
        }
        xhr.withCredentials = true;
    },
});
