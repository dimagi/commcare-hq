function(key, values, rereduce) {
    // these lines magically import our other javascript files.  DON'T REMOVE THEM!
    // !code util/schema.js
    // !code util/reconcile.js
    
    if (key!=null || rereduce) {
        return reconcile_model(values);
    } else {
        // in the null key/non-reduce state we don't want to output anything meaningful
        // as it will reduce on everything here.
        return {"#export_tag_value": null, "fail_reason": "empty export tag"};
    }
}