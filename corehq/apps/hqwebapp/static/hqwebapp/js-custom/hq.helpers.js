
var hash = window.location.hash;
// hack to prevent the default hash scroll behavior when using hash-tabs
//http://stackoverflow.com/questions/3659072/jquery-disable-anchor-jump-when-loading-a-page#answer-13349759
if (hash && $('.nav-tabs a[data-toggle="hash-tab"]a[href="' + hash + '"]').length > 0) {
    $('ul.nav a[href="' + hash + '"]').tab('show');
    window.scrollTo(0, 0);
    setTimeout(function() {
        window.scrollTo(0, 0);
    }, 1);
}

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
        form.find('.disable-on-submit').prop('disabled',true).addClass('disabled');
    });

    // now you can use data-toggle=hash-tab instead of the normal data-toggle=tab to persist the current open tab when
    // reloading a page or links to people. It also lets you have smart urls that leverage hashes
    // http://stackoverflow.com/questions/12131273/twitter-bootstrap-tabs-url-doesnt-change#answer-12138756
    $('.nav-tabs a[data-toggle="hash-tab"]').click(function (e) {
        e.preventDefault();
        $(this).tab('show');
        var scrollmem = $('body').scrollTop();
        window.location.hash = this.hash;
        $('html,body').scrollTop(scrollmem);
    });

    $(document).on('click', '.notification-close-btn', function() {
        var note_id = $(this).data('note-id');
        var post_url = $(this).data('url');
        $.post(post_url, {note_id: note_id});
        $(this).parents('.alert').hide(150);
    });
});

$.fn.hqHelp = function () {
    var self = this;
    self.each(function(i) {
        var $helpElem = $($(self).get(i));
        $helpElem.find('i').popover();
        $helpElem.click(function () {
            if ($helpElem.find('i').attr('data-trigger') != 'hover') {
                $(this).toggleClass('on');
            }
            if ($(this).hasClass('no-click')) {
                return false;
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
}
