var allowNumeric = function (event) {
    // Allow: backspace, delete, tab and escape
    if ( event.keyCode == 46 || event.keyCode == 8 || event.keyCode == 9 || event.keyCode == 27 ||
        // Allow: Ctrl,Alt,Cmd+anything
            event.ctrlKey === true || event.metaKey === true || event.altKey === true ||
        // Allow: home, end, left, right
            (event.keyCode >= 35 && event.keyCode <= 39)) {
        // let it happen, don't do anything
        return true;
    }
    else {
        // Ensure that it is a number and stop the keypress
        if (((event.keyCode < 48 || event.keyCode > 57) && (event.keyCode < 96 || event.keyCode > 105 )) || event.shiftKey == true) {
            return false;
        }
    }
};