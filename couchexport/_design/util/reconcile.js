var depth = 0;

function reconcile(type1, type2) {
    if (depth > 20)
        return log("Recursion depth too high!!!!");
    depth += 1;
    var type;

    var kind1 = get_kind(type1);
    var kind2 = get_kind(type2);

    if (kind1 != kind2) {
        if(kind2 == "null") {
        /* if someone calls reconcile(type, null),
    then swap it to be reconcile(null, type) */
            var tmp = kind2;
            kind2 = kind1;
            kind1 = tmp;
            tmp = type2;
            type2 = type1;
            type1 = tmp;
        }
        if(kind1 == "null") {
            if(kind2 == "list") {
                type = [reconcile_list(type2)];
            }
            else if(kind2 == 'dict') {
                type = {};
                for (var key in type2) {
                    type[key] = reconcile(null, type2[key]);
                }
            }
            else {
                type = type2;
            }
        }
        else if (kind1 == 'list') {
            type = reconcile(type1, [type2]);
        }
        else if (kind2 = 'list') {
            type = reconcile([type1], type2)
        }
        else {
            log("Cannot Reconsile!!");
            type = null;
        }
    }
    else {
        if(kind1 == 'dict') {
            type = {};
            for(var key in type1) {
                type[key] = null;
            }
            for(var key in type2) {
                type[key] = null;
            }
            for(var key in type) {
                type[key] = reconcile(type1[key], type2[key]);
            }
        }
        else if(kind1 == 'list') {
            type = [reconcile(reconcile_list(type1), reconcile_list(type2))];
        }
        else if(kind1 == 'null') {
            type = null;
        }
        else {
            type = "string";
        }
    }
    if (depth > 10) {
        log(depth);
        log(kind1 + ":\n\t" + uneval(type1));
        log(kind2 + ":\n\t" + uneval(type2));
        log(uneval(type));
    }
    depth -= 1;
    if (typeof type == "undefined") log("type undefined");
    return type;
}

function reconcile_list(types) {
    var type = null;
    for(var i in types){
        type = reconcile(type, types[i]);
    }
    return type;
}