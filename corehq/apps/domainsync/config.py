from django.conf import settings
from dimagi.utils.modules import to_function
import copy
from dimagi.utils.couch.database import get_db

def _extract_domains(doc):
    if "domain" in doc and doc["domain"]:
        return [doc["domain"]]
    elif "domains" in doc and doc["domains"]:
        return doc["domains"]
    return []

class DocumentTransform():
    # for coupling reasons, we have to bundle the original document 
    # with its attachments so that we can properly deal with it
    # across databases.
    # We also need the source database to fetch the attachment
    def __init__(self, doc, database):
        self._attachments = {}
        self.attachments = {}
        self.database = database
        if "_attachments" in doc and doc['_attachments']:
            self._attachments = doc["_attachments"]
            del doc["_attachments"]
            self.attachments = dict((k, self.database.fetch_attachment(doc["_id"], k)) for k in self._attachments)
        self.doc = doc

class TargetSyncConfig():
    
    def __init__(self, target, transform):
        self.domain = target
        self.transform_function = to_function(transform, failhard=True)
    
    def update_domains(self, doc, sourcedomain):
        if "domain" in doc and doc["domain"] == sourcedomain:
            doc["domain"] = self.domain
        elif "domains" in doc and sourcedomain in doc["domains"]:
            doc["domains"].remove(sourcedomain)
            doc["domains"].append(self.domain)
        else:
            raise ValueError("Source domain %s not found in doc %s!" % (sourcedomain, doc))
    
    def transform(self, doc, sourcedomain, sourcedb):
        self.update_domains(doc, sourcedomain)
        pretransform = DocumentTransform(doc, sourcedb)
        return self.transform_function(pretransform)
        
class DomainSyncConfig():
    """
    Initializes the object that deals with syncing domains. In your settings 
    you should define:
         
        DOMAIN_SYNCS = { sourcedomain1: { "domain": targetdomain1,
                                          "transform": path.to.transformfunction1 },
                         sourcedomain2: {...} }
    
    in your settings file.
    """
    
    def __init__(self):
        self.mapping = {}
        self.old_database = get_db()
        if hasattr(settings, "DOMAIN_SYNC_DATABASE_NAME"):
            # match a slash, followed by words or underscores
            # followed by the end of the string
            #re.sub("(?<=/)(\w_-)+$", settings.DOMAIN_SYNC_DATABASE_NAME, self.old_database.uri)
            self.database = self.old_database.server.get_or_create_db(settings.DOMAIN_SYNC_DATABASE_NAME)
        if hasattr(settings, "DOMAIN_SYNCS"):
            for domain, targetconfig in settings.DOMAIN_SYNCS.items():
                self.mapping[domain] = TargetSyncConfig(**targetconfig)
    
    def get_transforms(self, doc):
        transforms = []
        # always sync certain global documents
        if "doc_type" in doc and doc["doc_type"] == "CommCareBuild":
            return [DocumentTransform(doc, self.old_database)]
        
        for domain in _extract_domains(doc):
            if domain in self.mapping:
                doccopy = copy.deepcopy(doc)
                transformed = self.mapping[domain].transform(doccopy, domain, self.old_database)
                if transformed:
                    transforms.append(transformed)
        return transforms
    
    def save(self, transform):
        return save(transform, self.database)
        

def save(transform, database):
    # this is a fancy save method because we do some special casing
    # with the attachments
    database.save_doc(transform.doc, force_update=True)
    for k, attach in transform.attachments.items():
        database.put_attachment(transform.doc, attach, name=k, 
                                content_type=transform._attachments[k]["content_type"])
    

global_config = DomainSyncConfig()