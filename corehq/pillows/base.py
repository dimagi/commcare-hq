from pillowtop.listener import AliasedElasticPillow
from dimagi.utils.decorators.memoized import memoized


class HQPillow(AliasedElasticPillow):
    default_mapping = None

    def __init__(self, **kwargs):
        super(HQPillow, self).__init__(**kwargs)

    @memoized
    def calc_meta(self):
        """
        override of the meta calculator since we're separating out all the types,
        so we just do a hash of the "prototype" instead to determind md5
        """
        return self.calc_mapping_hash(self.default_mapping)

    def get_domain(self, doc_dict):
        """
        A cache/buffer for the _changes feed situation for xforms.
        """
        return doc_dict.get('domain', None)

    def get_type_string(self, doc_dict):
        return self.es_type

    def get_mapping_from_type(self, doc_dict):
        """
        Define mapping uniquely to the domain_type document.
        See below on why date_detection is False

        NOTE: DO NOT MODIFY THIS UNLESS ABSOLUTELY NECESSARY. A CHANGE BELOW WILL GENERATE A NEW
        HASH FOR THE INDEX NAME REQUIRING A REINDEX+RE-ALIAS. THIS IS A SERIOUSLY RESOURCE
        INTENSIVE OPERATION THAT REQUIRES SOME CAREFUL LOGISTICS TO MIGRATE
        """
        #the meta here is defined for when the case index + type is created for the FIRST time
        #subsequent data added to it will be added automatically, but date_detection is necessary
        # to be false to prevent indexes from not being created due to the way we store dates
        #all are strings EXCEPT the core case properties which we need to explicitly define below.
        #that way date sort and ranges will work with canonical date formats for queries.
        return {
            self.get_type_string(doc_dict): self.default_mapping
        }

