from __future__ import absolute_import
from collections import OrderedDict
import re
import os
import json

from corehq.util.quickcache import quickcache
from dimagi.ext.jsonobject import JsonObject, StringProperty, ListProperty, DictProperty
from corehq.apps.reports.sqlreport import DataFormatter
import six
from six.moves import range
from six.moves import map


@quickcache(['domain'], timeout=5 * 60)
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


def get_domains_with_next(domain_name, value_chain=None):
    configuration = get_domain_configuration(domain_name).by_type_hierarchy
    if value_chain:
        configuration = [x for x in configuration if x['val'] == value_chain]
    domains = []
    for chain in configuration:
        domains.extend(chain.next)
    return domains


def get_domains(domain_name):
    domains = get_domains_with_next(domain_name)
    return list({'val': d.val, "text": d.text} for d in domains)


def get_pracices(domain_name, value_chain=None):
    domains = get_domains_with_next(domain_name, value_chain)
    practices = []
    for domain in domains:
        practices.extend(domain.next)
    return list({'val': p.val, "text": p.text} for p in practices)


def _chunks(l, n):
    return [l[i:i+n] for i in range(0, len(l), n)]


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
                    missing_rows[key] = {'0', '1', '2'}.difference({row[-1]})
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
            sum_of_elements = sum([element['html'] for element in row[1:]])
            sum_of_elements = (100.0 / sum_of_elements) if sum_of_elements else 0

            result = [disp_name]

            for element in row[1:]:
                result.append(six.text_type(round(element['html'] * sum_of_elements)) + '%')
            yield result

            for value in chunk:
                formatted_row = self._format.format_row(value[1])
                if self.filter_row(value[0], formatted_row):
                    result = [formatted_row[0]['html']]
                    result.extend([element['html'] for element in formatted_row[1:]])
                    yield result


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

        for i in range(0, max([len(element) for element in data]) - 2):
            range_groups[0].append(0)
            range_groups[1].append(0)
            range_groups[2].append(0)
            range_groups[3].append(0)

        for row in data:
            for idx, practice in enumerate(row[2:], 1):
                if practice.get('sort_key') == 'N/A':
                    continue
                group = self.group_level(practice)
                if idx < len(row) - 1:
                    range_groups[group][idx] += 1

        for group in range_groups:
            for idx, row in enumerate(group[1:], 1):
                percent = 100 * float(group[idx]) / float(len(data))
                group[idx] = "%.2f%%" % percent
        return range_groups


class TableCardDataIndividualFormatter(DataFormatter):

    def first_column_format(self, x, table_card_group_by):
        if table_card_group_by == 'group_name':
            return x
        else:
            group_by = 'Groups'
            if table_card_group_by == 'group_leadership':
                group_by = 'Leadership'

            if int(x) == 0:
                return 'All Male %s' % group_by
            elif int(x) == 1:
                return 'Mixed %s' % group_by
            elif int(x) == 2:
                return 'All Female %s' % group_by

    def calculate_total_column(self, row):
        TAG_RE = re.compile(r'<[^>]+>')

        def remove_tags(text):
            return TAG_RE.sub('', text)

        num_practices = 0
        total_practices = 0
        for prop in row:
            if prop.get('sort_key') == 'N/A':
                continue
            values = list(map(int, re.findall(r'\d+', remove_tags(prop['html']))))
            num_practices += values[0]
            total_practices += values[1]

        value = "%d/%d (%.2f%%)" % ((num_practices or 0), total_practices,
                                    100 * int(num_practices or 0) / float(total_practices or 1))
        return {'sort_key': value, 'html': value}

    def _init_row(self, practices):
        row = {}
        for practice in practices:
            row[practice.val] = None
        return row

    def format(self, data, keys=None, group_by=None, domain=None, practices=None):
        practices = practices or []
        groups = set()
        for row in data.keys():
            groups.add(row[0])

        groups = sorted(list(groups))
        result = OrderedDict()
        for group in groups:
            result[group] = self._init_row(practices)

        for key, row in data.iteritems():
            formatted_row = self._format.format_row(row)
            result[key[0]][row['practices']] = formatted_row[1]

        for key, row in result.items():
            formatted_row = []
            for practice in practices:
                value = row[practice.val]
                if value is None:
                    formatted_row.append({'html': 'N/A', 'sort_key': 'N/A'})
                else:
                    formatted_row.append(value)
            total_column = self.calculate_total_column(formatted_row)
            name = self.first_column_format(key, group_by)
            res = [{'html': name, 'sort_key': name}, total_column]
            res.extend(formatted_row)
            yield res


class TableCardDataGroupsIndividualFormatter(TableCardDataIndividualFormatter):

    def format(self, data, keys=None, group_by=None, domain=None, practices=None):
        practices = practices or []
        groups = set()
        id_to_name = {}
        for row in sorted(data.keys()):
            groups.add(row[0])
            id_to_name[row[0]] = u'{} ({})'.format(row[1].title(), row[2])

        groups = sorted(list(groups), key=lambda r: id_to_name[r])
        result = OrderedDict()
        for group in groups:
            result[group] = self._init_row(practices)

        for key, row in data.iteritems():
            formatted_row = self._format.format_row(row)
            result[key[0]][row['practices']] = formatted_row[1]
            id_to_name[key[0]] = u'{} ({})'.format(key[1], key[2])

        for key, row in result.items():
            formatted_row = []
            for practice in practices:
                value = row[practice.val]
                if value is None:
                    formatted_row.append({'html': 'N/A', 'sort_key': 'N/A'})
                else:
                    formatted_row.append(value)
            total_column = self.calculate_total_column(formatted_row)
            res = [{'html': id_to_name[key], 'sort_key': id_to_name[key]}, total_column]
            res.extend(formatted_row)
            yield res
