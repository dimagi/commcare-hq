function(keys, values, rereduce) {
	var properties = [];

	for (var i = 0; i < values.length; ++i) {
		for (var action_index in values[i]) {
			action = values[i][action_index];	
			for(var k in action.updated_known_properties) {
				if (properties.indexOf(k) == -1) {
					properties.push(k);
				}
			}
		}
	}

	return properties;
}