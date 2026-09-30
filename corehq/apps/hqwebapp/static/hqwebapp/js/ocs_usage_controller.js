import $ from "jquery";
import initialPageData from "hqwebapp/js/initial_page_data";

function bindUsageController(widget) {
    let usageState;

    function updateWidget() {
        if (usageState.limit === -1) {
            widget.disabled = false;
            widget.bannerMessage = '';
            return;
        }
        widget.disabled = usageState.used >= usageState.limit;
        widget.bannerStyle = widget.disabled ? 'error' : 'warning';
        if (usageState.limit === 0) {
            widget.bannerMessage = gettext("CommCare Companion is not included in your current subscription.");
        } else if (widget.disabled) {
            widget.bannerMessage = gettext(
                "You've reached your chat limit for this month. Your allowance resets on the 1st of next month (UTC).",
            );
        } else if (usageState.used >= usageState.limit * 0.8) {
            const percentUsed = Math.floor(100 * usageState.used / usageState.limit);
            widget.bannerMessage = interpolate(gettext(
                "You've used %(percent)s%% of your chat messages this month.",
            ), {percent: percentUsed}, true);
        } else {
            widget.bannerMessage = '';
        }
    }

    function applyUsageState(value) {
        usageState = value;
        updateWidget();
    }

    function requestUsage(method) {
        return $.ajax({
            url: initialPageData.reverse('chat_quota'),
            method: method,
            dataType: 'json',
            cache: false,
        });
    }

    function showUsageError() {
        widget.disabled = true;
        widget.bannerStyle = 'error';
        widget.bannerMessage = gettext(
            "We couldn't check your chat allowance. Please close and reopen the chat to try again.",
        );
    }

    function handleWidgetOpen() {
        requestUsage('GET').done(applyUsageState).fail(showUsageError);
    }

    function handleMessageSent() {
        if (usageState?.limit === -1) {
            return;
        }
        requestUsage('POST').done(applyUsageState).fail(showUsageError);
    }

    widget.addEventListener('ocs:open', handleWidgetOpen);
    widget.addEventListener('ocs:message:sent', handleMessageSent);
    // In case the widget is already open when the page loads
    if (widget.visible === true) {
        handleWidgetOpen();
    }
}

$(function () {
    const widget = document.querySelector('open-chat-studio-widget');
    if (widget) {
        bindUsageController(widget);
    }
});
