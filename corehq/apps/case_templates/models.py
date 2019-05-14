# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals

import uuid
from collections import OrderedDict
from xml.etree import cElementTree as ElementTree

from django.db import models
from django.utils.functional import cached_property

from six import StringIO

from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.xml import V2, V2_NAMESPACE
from casexml.apps.phone.xml import get_case_xml

from corehq.blobs import CODES, get_blob_db
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors


class CaseTemplate(models.Model):
    template_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    domain = models.CharField(max_length=256, null=False, blank=False, db_index=True)
    name = models.CharField(max_length=256, null=False)
    comment = models.TextField(null=True)

    def __repr__(self):
        return (
            "CaseTemplate("
            "template_id='{self.template_id}', "
            "domain='{self.domain}', "
            "name='{self.name}', "
            "comment='{self.comment}'"
            ")"
        ).format(self=self)

    @classmethod
    def create(cls, domain, root_case_id, name, comment=None):
        template = cls.objects.create(domain=domain, name=name, comment=comment)
        template.save_template_xml(cls._generate_case_xml(domain, root_case_id))
        return template

    @staticmethod
    def _generate_case_xml(domain, root_case_id):
        """Returns a blob of XML containing all the cases in the case hierarchy starting with `root_case_id`
        """
        root_case = CaseAccessors(domain).get_case(root_case_id)
        case_xml_blocks = (
            get_case_xml(case, ('create', 'update'), V2) for case in get_case_hierarchy(root_case)
        )
        return "<template-cases>{}</template-cases>".format("".join(case_xml_blocks))

    @property
    def _blob_key(self):
        return "case-template-{}-{}".format(self.domain, self.template_id)

    def save_template_xml(self, case_xml):
        """saves the case_xml to the blobdb
        """
        blob_meta_args = {
            "name": "{}.xml".format(self._blob_key),
            "parent_id": self.template_id,
            "domain": self.domain,
            "type_code": CODES.case_template,
            "key": self._blob_key,
        }
        return get_blob_db().put(StringIO(case_xml), **blob_meta_args)

    @cached_property
    def prototype_cases(self):
        """Dict of cases, keyed by case ID, contained in the template
        """
        case_blocks = (
            CaseBlock.from_xml(node)
            for node in self._get_template_xml().findall("{%s}case" % V2_NAMESPACE)
        )
        return OrderedDict((case.case_id, case) for case in case_blocks)

    def num_cases(self):
        return len(self.prototype_cases)

    def _get_template_xml(self):
        """get case xml from the blobdb
        """
        with get_blob_db().get(self._blob_key) as file_obj:
            template_xml = ElementTree.fromstring(file_obj.read())
        return template_xml


class CaseTemplateInstanceCase(models.Model):
    template = models.ForeignKey(CaseTemplate, on_delete=models.CASCADE, related_name='instance_cases')
    case_id = models.CharField(max_length=255, unique=True, db_index=True)


def get_case_hierarchy(case):
    new_subcases = list(case.get_subcases())
    all_subcases = []
    while new_subcases:
        all_subcases.extend(new_subcases)
        new_subcases = [
            subcase
            for new_case in new_subcases
            for subcase in list(new_case.get_subcases())
            if list(new_case.get_subcases())
        ]
    return [case] + list(all_subcases)
