

def create_backup(filename, attachment):
    """Create a backup from a file and attachment"""
    # for the time being, this needs to be in here because of cyclical 
    # references
    from backups.models import Backup, BackupUser
    backup = Backup(attachment=attachment)
    usernames, device_id = _get_backup_metadata(attachment)
    backup.device_id = device_id
    domain = attachment.submission.domain
    users = []
    for username in usernames:
        users.append(BackupUser.objects.get_or_create(domain=domain, 
                                                      username=username)[0])
    backup.users = users
    backup.save()
    
def _get_backup_metadata(attachment):
    """Gets the users, device_id, and whatever else we desire to extract from 
       a  backup file."""
    # TODO - parse out the xml and set the right parameters
    return [["demo_user", "cory", "drew"], "abciseasyas123"]
    