from corehq.apps.crud.dispatcher import BaseCRUDAdminInterfaceDispatcher

class HQAnnouncementAdminInterfaceDispatcher(BaseCRUDAdminInterfaceDispatcher):
    prefix = 'announcements_admin_interface'
    map_name = "ANNOUNCEMENTS_ADMIN_INTERFACE_MAP"
