from corehq.extensions.interface import CommCareExtensions

extension_manager = CommCareExtensions()
extension_point = extension_manager.extension_point
hook = extension_manager.registry
