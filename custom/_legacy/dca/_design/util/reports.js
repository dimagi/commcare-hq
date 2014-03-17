/*
 * use this to make sure you loaded the reports module properly
 */

function hello_reports() {
    log("hello reports!");
}

/*
 * Function/Class to represent a report
 */
 
function report(name, values) {
    this.name = name;
    this.values = values;
}

 
/*
 * Function/Class to represent a value in a report
 */

function reportValue(num, denom, slug, hidden, description, display_name) {
    this.num = num;
    this.denom = denom;
    this.slug = slug;
    // this param is optional, defaulting to false
    if (hidden!=null) {
        this.hidden = hidden;
    } else {
        this.hidden = false;
    }
    if (description != null) {
        this.description = description;
    } else {
        this.description = null;
    }
    // the display name describes the slug
    if (display_name != null) {
        this.display_name = display_name;
    } else {
        this.display_name = null;
    }
    
}


/*
 * Performs reduce aggregation and adds the report name.
 */
function reduce_common(keys, values, rereduce, report_name) {
    totals = {};
    for (var i = 0; i < values.length; i++) {
        result = rereduce ? values[i].values : values[i];
        for (var j = 0; j < result.length; j++) {
            rep_val = result[j];
            if (!totals.hasOwnProperty(rep_val.slug)) {
                totals[rep_val.slug] = rep_val;
            } else {
                old_val = totals[rep_val.slug]
                old_val.num += rep_val.num;
                old_val.denom += rep_val.denom;
            }
        }
    }
    // convert back to an array
    ret = [];
    for (key in totals) {
        ret.push(totals[key]);
    }
    return new report(report_name, ret);
}
/*
 * Check for name existing within drugs prescribed
 */
function check_drug_name(drugs_prescribed, name_to_check) {
	bool_name_good = 0;
	for (var i = 0; i < drugs_prescribed.length && !bool_name_good; i++) {
        this_drug = drugs_prescribed[i];
        if (exists(this_drug["name"],name_to_check)) {
        	bool_name_good =  1;
        } else {
        	bool_name_good =  0;
        }
    }
    return bool_name_good;
}
/*
 * Returns boolean for whether a drug prescribed matches an intended type and formulation
 */
function check_drug_type(drugs_prescribed, type_to_check, formulation_to_check) {
    bool_check_good = 0;
    for (var i = 0; i < drugs_prescribed.length && !bool_check_good; i++) {
        this_drug = drugs_prescribed[i];
        
   		for (var j = 0; j < this_drug["types"].length && !bool_check_good; j++) {
   			if (exists(this_drug["types"],type_to_check) && (formulation_to_check == null)) {
   				bool_check_good =  1;
   			} else if (exists(this_drug["types"],type_to_check) && formulation_to_check) {
   			   	if(exists(this_drug["formulations"],formulation_to_check)) {
   					bool_check_good =  1;
   				} else {
   					bool_check_good =  0;
   				}  			
   			} else {
   				bool_check_good =  0;
   			}
   		}
   	}	
   	return bool_check_good
}
	    