var HTML5_TEXT_INPUT_FIELD_SELECTOR = 
        'input:text,input:password,input[type=email],' +
        'input[type=number],input[type=search],input[type=tel],' +
        'input[type=time],input[type=url]';

/**
 * Utility function to trigger a key press event for each character
 * in a string.  Each character will be triggered 'keyTiming'
 * milliseconds apart.  The onComplete function will be called 
 * 'keyTiming' milliseconds after the last key is triggered.
 */
function triggerKeyEventsForString(field, str, keyTiming, 
                                    triggerFocus, onComplete) {
    if (field && str) {
        field = $(field);
        triggerFocus = Boolean(triggerFocus);

        if (triggerFocus) {
            field.trigger('focus');
        }

        var     keyCode = str.charCodeAt(0);

        triggerKeyEvents(field, keyCode);

        if (str.length > 1) {
            setTimeout(function() {
                            triggerKeyEventsForString(field,
                                                      str.substring(1),
                                                      keyTiming, false,
                                                      onComplete);
                        }, keyTiming);
        }
        else {
            if (jQuery.isFunction(onComplete)) {
                setTimeout(function() {
                                    onComplete(field);
                                }, keyTiming);
            }
        }
    }
}

/**
 * Utility function to trigger a key event for a given key code.
 */
function triggerKeyEvents(field, keyCode, shiftKey, ctrlKey) {
    field = $(field);
    shiftKey = Boolean(shiftKey);
    ctrlKey = Boolean(ctrlKey);

    field.simulate("keydown", { keyCode: keyCode,
                                ctrlKey: ctrlKey,
                                shiftKey: shiftKey });
    field.simulate("keypress", { keyCode: keyCode,
                                 ctrlKey: ctrlKey,
                                 shiftKey: shiftKey });

    if (field.is(HTML5_TEXT_INPUT_FIELD_SELECTOR)) {
        applyKeyCodeToValue(field, keyCode);
    }

    field.simulate("keyup", { keyCode: keyCode,
                              ctrlKey: ctrlKey,
                              shiftKey: shiftKey });
}

/*
 * Internal function to simulate a key being typed into an edit 
 * field for testing purposes.  Tries to handle cases like 
 * 'backspace' or 'arrow key'.  It's assumed that the cursor is
 * always at the end of the field.
 */
function applyKeyCodeToValue(field, keyCode) {
    field = $(field);

    if ((keyCode >= 32) && (keyCode <= 126)) {
        field.val(field.val() + String.fromCharCode(keyCode));
    }
    else {
        switch(keyCode) {
            case 8:                                 // Backspace
                var     val = field.val();

                if (val.length) {
                    field.val(val.substring(0, val.length - 1));
                }
                break;

            default:
                break;
        }
    }
}
