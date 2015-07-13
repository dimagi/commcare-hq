from corehq.apps.commtrack.const import RequisitionActions


class UserRequisitionRoles(object):
    REQUESTER = 'commtrack_requester'
    APPROVER = 'commtrack_approver'
    SUPPLIER = 'commtrack_supplier'
    RECEIVER = 'commtrack_receiver'

    @classmethod
    def get_user_role(cls, action_type):
        return {
            RequisitionActions.REQUEST: cls.REQUESTER,
            RequisitionActions.APPROVAL: cls.APPROVER,
            RequisitionActions.FULFILL: cls.SUPPLIER,
            RequisitionActions.RECEIPTS: cls.RECEIVER,
        }[action_type]
