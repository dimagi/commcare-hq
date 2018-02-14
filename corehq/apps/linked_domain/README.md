# Linking Domains

* Ability to sync models between two domains (master domain -> linked domain)
* Can be within the same HQ instance or between remote instances.

# Remote linking

### On 'master domain':

```
DomainLink.link_domains('https://url.of.linked.hq/a/linked_domain_name', 'master_domain_name')
```

This gets used as a permissions check during remote requests to ensure
that the remote domain is allowed to sync from this domain.

### On 'linked domain'

```
remote_details = RemoteLinkDetails(
    url_base='https://url.of.master.hq',
    username='username@email.com',
    api_key='api key for username'
)
DomainLink.link_domains('linked_domain_name', 'master_domain_name', remote_details)
```
