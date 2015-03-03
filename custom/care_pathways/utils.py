from collections import OrderedDict
import re
import os
import json
from jsonobject import JsonObject, StringProperty, ListProperty, DictProperty
from corehq.apps.reports.sqlreport import DataFormatter
from dimagi.utils.decorators.memoized import memoized

@memoized
def get_domain_configuration(domain):
    with open(os.path.join(os.path.dirname(__file__), 'resources/%s.json' % (domain))) as f:
        _loaded_configuration = json.loads(f.read())
        return DomainConfiguration(
            geography_hierarchy=_loaded_configuration['geography_hierarchy'],
            by_type_hierarchy=[ByTypeHierarchyRecord(d) for d in _loaded_configuration['by_type_hierarchy']]
        )

def is_mapping(prop, domain):
    return any(d['val'] == prop for d in get_mapping(domain))

def is_domain(prop, domain):
    return any(d['val'] == prop for d in get_domains(domain))

def is_practice(prop, domain):
    return any(d['val'] == prop for d in get_pracices(domain))

def get_mapping(domain_name):
    value_chains = get_domain_configuration(domain_name).by_type_hierarchy
    return list({'val': vc.val, "text": vc.text} for vc in value_chains)

def get_domains_with_next(domain_name):
    configuration = get_domain_configuration(domain_name).by_type_hierarchy
    domains = []
    for chain in configuration:
        domains.extend(chain.next)
    return domains


def get_domains(domain_name):
    domains = get_domains_with_next(domain_name)
    return list({'val': d.val, "text": d.text} for d in domains)


def get_pracices(case):
    domains = get_domains_with_next(case)
    practices = []
    for domain in domains:
        practices.extend(domain.next)
    return list({'val': p.val, "text": p.text} for p in practices)


def _chunks(l, n):
    return [l[i:i+n] for i in xrange(0, len(l), n)]


class ByTypeHierarchyRecord(JsonObject):
    val = StringProperty()
    text = StringProperty()
    next = ListProperty(lambda: ByTypeHierarchyRecord, exclude_if_none=True)


class DomainConfiguration(JsonObject):
    geography_hierarchy = DictProperty()
    by_type_hierarchy = ListProperty(ByTypeHierarchyRecord)


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
                    tmp_missing.update({dict_key: dict(all=0, some=0, none=0, gender=missing_val)})
            data.update(tmp_missing)
        if len(group_by) - 1 == 1:
            f = lambda x: (x[0][0], x[0][1])
        elif len(group_by) - 1 == 2:
            f = lambda x: (x[0][0], x[0][1], x[0][2])
        elif len(group_by) - 1 == 3:
            f = lambda x: (x[0][0], x[0][1], x[0][2], x[0][3])
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
                value_chains = get_domain_configuration(domain).by_type_hierarchy

                def find_name(list, deep):
                    for element in list:
                        if deep == len(val[0])-2 and val[0][deep] == element.val:
                            return element.text
                        elif val[0][deep] == element.val:
                            return find_name(element.next, deep+1)

                disp_name = find_name(value_chains, 0)
            row = self._format.format_row(group_row)
            sum = row[1]['html'] + row[2]['html'] + row[3]['html']
            yield [disp_name, unicode(round(row[1]['html'] * 100.0 / sum)) + '%',
                   unicode(round(row[2]['html'] * 100.0 / sum)) + '%',
                   unicode(round(row[3]['html'] * 100.0 / sum)) + '%']
            for value in chunk:
                formatted_row = self._format.format_row(value[1])
                if self.filter_row(value[0], formatted_row):
                    yield [formatted_row[0]['html'], formatted_row[1]['html'], formatted_row[2]['html'],
                           formatted_row[3]['html']]


class TableCardDataGroupsFormatter(DataFormatter):

    def group_level(self, row):
        TAG_RE = re.compile(r'<[^>]+>')

        def remove_tags(text):
            return TAG_RE.sub('', text)

        practice_percent = map(int, re.findall(r'\d+', remove_tags(row['html'])))[2]
        if 76 <= practice_percent <= 100:
            return 0
        elif 51 <= practice_percent < 76:
            return 1
        elif 26 <= practice_percent < 51:
            return 2
        else:
            return 3


    def format(self, data, keys=None, group_by=None):
        range_groups = [
            ['A'],
            ['B'],
            ['C'],
            ['D'],
        ]
        rows_dict = dict()
        for key, row in data.items():
            formatted_row = self._format.format_row(row)
            if not rows_dict.has_key(formatted_row[0]):
                rows_dict[formatted_row[0]] = []
            rows_dict[formatted_row[0]].append(formatted_row[1])

        for i in xrange(0, len(rows_dict[rows_dict.keys()[0]])):
            range_groups[0].append(0)
            range_groups[1].append(0)
            range_groups[2].append(0)
            range_groups[3].append(0)

        for key, row in rows_dict.items():
            for idx, practice in enumerate(row, 1):
                group = self.group_level(practice)
                if idx < len(range_groups[group]):
                    range_groups[group][idx] += 1
        all_rows = len(rows_dict)

        for group in range_groups:
            for idx, row in enumerate(group[1:], 1):
                percent = 100 * float(group[idx]) / float(all_rows)
                group[idx] = "%.2f%%" % percent
        return range_groups

class TableCardDataIndividualFormatter(DataFormatter):

    def calculate_total_column(self, row):
        TAG_RE = re.compile(r'<[^>]+>')

        def remove_tags(text):
            return TAG_RE.sub('', text)

        num_practices = 0
        total_practices = 0
        for prop in row:
            values = map(int, re.findall(r'\d+', remove_tags(prop['html'])))
            num_practices += values[0]
            total_practices += values[1]

        return "%d/%d (%.2f%%)" % ((num_practices or 0), total_practices, 100 * int(num_practices or 0) / float(total_practices or 1))

    def format(self, data, keys=None, group_by=None, domain=None):
        rows_dict = OrderedDict()
        tmp_data = OrderedDict()
        sorted_data = []
        value_chains = get_domain_configuration(domain).by_type_hierarchy
        for key, row in data.items():
            to_list = list(key)

            def find_name(list, deep):
                for element in list:
                    if deep == len(key)-3 and key[deep+1] == element.val:
                        return element.text
                    elif key[deep+1] == element.val:
                        return find_name(element.next, deep+1)

            name = find_name(value_chains, 0)
            to_list[2] = name
            tmp_data.update({tuple(to_list): row})
        if tmp_data:
            sorted_data = sorted(tmp_data.items(), key=lambda x: (x[0][0], x[0][2]))

        for row in sorted_data:
            formatted_row = self._format.format_row(row[1])
            if not rows_dict.has_key(formatted_row[0]):
                rows_dict[formatted_row[0]] = []
            rows_dict[formatted_row[0]].append(formatted_row[1])

        min_length = min([len(item[1]) for item in rows_dict.items()])

        for key, row in rows_dict.items():
            total_column = self.calculate_total_column(row)
            res = [key, total_column]
            res.extend(row[0:min_length])
            yield res
