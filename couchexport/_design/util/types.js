
function is_string(val) {
    return uneval(val)[0] == '"';
}

function are_equal(tag1, tag2) {
    if (is_string(tag1)) {
        return tag1 == tag2;
    } else if (is_string(tag2)) {
        // lists aren't strings
        return false;
    } else {
        if (tag1.length == tag2.length) {
            for (var i in tag1) {
                if (tag1[i] != tag2[i]) {
                    return false;
                }
            }
            return true; 
        } else {
            return false;
        }
    }
}

