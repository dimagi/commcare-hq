hqDefine("hqwebapp/js/hq.helpers", [
    'jquery',
    'knockout',
    'underscore',
    'analytix/js/google',
], function (
    $,
    ko,
    _,
    googleAnalytics
) {
    var clearAnnouncement = function (announcementID) {
        $.ajax({
            url: '/announcements/clear/' + announcementID,
        });
    };

    $('.page-level-alert').on('closed', function () {
        var announcement_id = $('.page-level-alert').find('.announcement-control').data('announcementid');
        if (announcement_id) {
            clearAnnouncement(announcement_id);
        }
    });

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
        var note_id = $(this).data('note-id');
        var post_url = $(this).data('url');
        $.post(post_url, {note_id: note_id});
        $(this).parents('.alert').hide(150);
    });

    if ($.timeago) {
        $.timeago.settings.allowFuture = true;
        $(".timeago").timeago();
    }

    window.onerror = function (message, file, line, col, error) {
        $.post('/jserror/', {
            message: message,
            page: window.location.href,
            file: file,
            line: line,
            stack: error ? error.stack : null,
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

    $.fn.hqHelp = function () {
        var self = this;
        self.each(function (i) {
            var $self = $(self),
                $helpElem = $($self.get(i)),
                $link = $helpElem.find('a');

            var options = {
                html: true,
                trigger: 'focus',
                container: 'body',
            };
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

    $.showMessage = function (message, level) {
        var $notice = $('<div />').addClass("alert fade in alert-block alert-full page-level-alert")
            .addClass("alert-" + level);
        var $closeIcon = $('<a />').addClass("close").attr("data-dismiss", "alert");
        $closeIcon.attr("href", "#").html("&times;");
        $notice.append($closeIcon);
        $notice.append(message);
        $(".hq-page-header-container").prepend($notice);
    };


    $.fn.addSpinnerToButton = function () {
        $(this).prepend('<i class="fa fa-refresh fa-spin icon-refresh icon-spin"></i> ');
    };


    $.fn.removeSpinnerFromButton = function () {
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
        this.removeClass('ko-template');
        $('.ko-loading').addClass('hide');
    };

    $.ajaxSetup({
        beforeSend: function (xhr, settings) {
            // Don't pass csrftoken cross domain
            // Ignore HTTP methods that do not require CSRF protection
            if (!/^(GET|HEAD|OPTIONS|TRACE)$/.test(settings.type) && !this.crossDomain) {
                var $csrf_token = $("#csrfTokenContainer").val();
                xhr.setRequestHeader("X-CSRFToken", $csrf_token);
            }
        },
    });

    // Return something so that hqModules understands that the module has been defined
    return 1;
});
