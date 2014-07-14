$(function() {
    // trick to give a select menu an initial value
    $('select[data-value]').each(function () {
        var val = $(this).attr('data-value');
        if (val) {
            $(this).find('option').removeAttr('selected');
            $(this).find('option[value="' + val + '"]').attr('selected', 'true');
        }
    });

    var clearAnnouncement = function (announcementID) {
        $.ajax({
            url: '/announcements/clear/' + announcementID
        });
    };

    $('.page-level-alert').bind('closed', function () {
        var announcement_id = $('.page-level-alert').find('.announcement-control').data('announcementid');
        if (announcement_id) {
            clearAnnouncement(announcement_id);
        }
    });

    // disable-on-submit is a class for form submit buttons so they're automatically disabled when the form is submitted
    $(document).on('submit', 'form', function(ev) {
        var form = $(ev.target);
        form.find('.disable-on-submit').disableButton();
        form.find('.disable-on-submit-no-spinner').disableButtonNoSpinner();
    });
    $(document).on('submit', 'form.disable-on-submit', function (ev) {
        $(ev.target).find('[type="submit"]').disableButton();
    });
    $(document).on('click', '.add-spinner-on-click', function(ev) {
        $(ev.target).addSpinnerToButton();
    });

    $(document).on('click', '.notification-close-btn', function() {
        var note_id = $(this).data('note-id');
        var post_url = $(this).data('url');
        $.post(post_url, {note_id: note_id});
        $(this).parents('.alert').hide(150);
    });
});

var oldHide = $.fn.popover.Constructor.prototype.hide;

$.fn.popover.Constructor.prototype.hide = function() {
    if (this.options.trigger === "hover" && this.tip().is(":hover")) {
        var that = this;
        setTimeout(function() {
            return that.hide.call(that, arguments);
        }, that.options.delay.hide);
        return;
    }
    oldHide.call(this, arguments);
};

$.fn.hqHelp = function () {
    var self = this;
    self.each(function(i) {
        var $helpElem = $($(self).get(i));
        $helpElem.find('i').popover({
            html: true,
            content: function() {
                return $('#popover_content_wrapper').html();
            }
        })
    });
};

$.showMessage = function (message, level) {
    $notice = $('<div />').addClass("alert fade in alert-block alert-full page-level-alert")
        .addClass("alert-" + level);
    var $closeIcon = $('<a />').addClass("close").attr("data-dismiss", "alert");
    $closeIcon.attr("href", "#").html("&times;");
    $notice.append($closeIcon);
    $notice.append(message);
    $(".hq-page-header-container").prepend($notice);
};


$.fn.addSpinnerToButton = function () {
    $(this).prepend('<i class="icon-refresh icon-spin"></i> ');
};


$.fn.disableButtonNoSpinner = function () {
    $(this).attr('disabled', 'disabled')
           .addClass('disabled');
};


$.fn.disableButton = function () {
    $(this).disableButtonNoSpinner();
    $(this).addSpinnerToButton();
};
