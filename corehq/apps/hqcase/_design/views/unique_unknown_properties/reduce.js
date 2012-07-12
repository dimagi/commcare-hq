function(keys, values, rereduce) {
	var properties = [];

	if (rereduce) {
		for (var i = 0; i < values.length; i++) {
			for (var j = 0; j < values[i].length; j++) {
				if (properties.indexOf(values[i][j]) == -1) {
					properties.push(values[i][j]);
				}				
			}
		}
	} else {
		for (var i = 0; i < values.length; i++) {
			for (var action_index in values[i]) {
				action = values[i][action_index];
				for(var k in action.updated_unknown_properties) {
					if (properties.indexOf(k) == -1) {
						properties.push(k);
					}
				}
			}
		}
	}
	
	return properties;
}