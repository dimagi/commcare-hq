from corehq.extensions.interface import CommCareExtensions

extension_manager = CommCareExtensions()

get_contributions = extension_manager.get_extension_point_contributions
