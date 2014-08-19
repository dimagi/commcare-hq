import os
import json
from corehq.apps.reports.sqlreport import DataFormatter

def get_domain_configuration(domain):
    with open(os.path.join(os.path.dirname(__file__), 'resources/%s.json' % (domain))) as f:
        return json.loads(f.read())

def is_mapping(prop, domain):
    return any(d['val'] == prop for d in get_mapping(domain))

def is_domain(prop, domain):
    return any(d['val'] == prop for d in get_domains(domain))

def is_practice(prop, domain):
    return any(d['val'] == prop for d in get_pracices(domain))

def get_mapping(domain_name):
    value_chains = get_domain_configuration(domain_name)['by_type_hierarchy']
    return list({'val': vc['val'], "text": vc['text']} for vc in value_chains)

def get_domains_with_next(domain_name):
    configuration = get_domain_configuration(domain_name)['by_type_hierarchy']
    domains = []
    for chain in configuration:
        domains.extend(chain['next'])
    return domains


def get_domains(domain_name):
    domains = get_domains_with_next(domain_name)
    return list({'val': d['val'], "text": d['text']} for d in domains)


def get_pracices(case):
    domains = get_domains_with_next(case)
    practices = []
    for domain in domains:
        practices.extend(domain['next'])
    return list({'val': p['val'], "text": p['text']} for p in practices)


def _chunks(l, n):
    return [l[i:i+n] for i in xrange(0, len(l), n)]


class CareDataFormatter(DataFormatter):

    def format(self, data, keys=None, group_by=None, domain=None, chunk_size=3):

        missing_rows = {}

        tmp_missing = {}
        if chunk_size == 3:
            for row in data:
                key = tuple(row[:-1])
                if key not in missing_rows:
                    missing_rows[key] = {0, 1, 2}.difference({row[-1]})
                else:
                    missing_rows[key] = missing_rows[key].difference({row[-1]})
            for k, v in missing_rows.iteritems():
                for missing_val in v:
                    dict_key = k + (missing_val,)
                    tmp_missing.update({dict_key:dict(all=0, some=0, none=0, gender=missing_val)})
            data.update(tmp_missing)
        if len(group_by)-1 == 1:
            f = lambda x: (x[0][0])
        elif len(group_by)-1 == 2:
            f = lambda x: (x[0][0], x[0][1])
        elif len(group_by)-1 == 3:
            f = lambda x: (x[0][0], x[0][1], x[0][2])
        else:
            f = lambda x: x
        chunks = _chunks(sorted(data.items(), key=f), chunk_size)
        for chunk in chunks:
            group_row = dict(all=0, some=0, none=0)
            disp_name = None
            for val in chunk:
                for k, v in val[1].iteritems():
                    if k in group_row:
                        group_row[k] += v
                value_chains = get_domain_configuration(domain)['by_type_hierarchy']

                def find_name(list, deep):
                    for element in list:
                        if deep == len(val[0])-2 and val[0][deep] == element['val']:
                            return element['text']
                        elif val[0][deep] == element['val']:
                            return find_name(element['next'], deep+1)

                disp_name = find_name(value_chains, 0)
            row = self._format.format_row(group_row)
            yield [disp_name, row[1]['html'], row[2]['html'], row[3]['html']]
            for value in chunk:
                formatted_row = self._format.format_row(value[1])
                if self.filter_row(value[0], formatted_row):
                    yield [formatted_row[0]['html'], formatted_row[1]['html'], formatted_row[2]['html'], formatted_row[3]['html']]

