from corehq.extensions.interface import CommCareExtensions

extension_manager = CommCareExtensions()
extension_point = extension_manager.extension_point
get_contributions = extension_manager.get_extension_point_contributions
