from datetime import datetime
import json
import feedparser
import time
import requests
from requests.auth import HTTPBasicAuth
from corehq.apps.commtrack.models import RequisitionCase
from custom.openlmis.exceptions import OpenLMISAPIException


class RssMetadata(object):

    def __init__(self, id, updated, metadata):
        self.id = id
        self.updated = updated
        self.metadata = metadata

    @classmethod
    def from_entry(cls, entry):
        id = entry['id']
        updated = datetime.fromtimestamp(time.mktime(entry['updated_parsed']))
        [content] = entry['content']
        metadata = json.loads(content['value'])
        return cls(id, updated, metadata)


class RssWrapper(object):

    def __init__(self, rss_meta):
        self.rss_meta = rss_meta

    @property
    def metadata(self):
        return self.rss_meta.metadata


class Facility(RssWrapper):

    @property
    def code(self):
        return self.metadata['code']

    @property
    def name(self):
        return self.metadata['name']

    @property
    def type(self):
        return self.metadata['facilityType']

    @property
    def latitude(self):
        return self.metadata.get('latitude', None)

    @property
    def longitude(self):
        return self.metadata.get('longitude', None)

    @property
    def parent_id(self):
        return self.metadata.get('parentFacility', None)


class FacilityProgramLink(RssWrapper):
    pass


class Product(object):

    def __init__(self, code, name, description, unit, category):
        self.code = code
        self.name = name
        self.description = description
        self.unit = unit
        self.category = category

    @classmethod
    def from_json(cls, json_rep):
        return cls(
            code=json_rep['productCode'],
            name=json_rep['productName'],
            description=json_rep['description'],
            unit=json_rep['unit'],
            category=json_rep['category'],
        )

class RequisitionStatus(RssWrapper):

    @property
    def requisition_id(self):
        return self.metadata['requisitionId']

    @property
    def requisition_status(self):
        return self.metadata['requisitionStatus']

    @property
    def order_id(self):
        return self.metadata.get('orderId', None)

    @property
    def order_status(self):
        return self.metadata.get('orderStatus', None)

    @property
    def emergency(self):
        return self.metadata.get('emergency', None)

    @property
    def start_date(self):
        return self.metadata.get('startDate', None)

    @property
    def end_date(self):
        return self.metadata.get('endDate', None)


class Program(object):

    def __init__(self, code, name, products=None):
        self.code = code
        self.name = name
        self.products = products or []

    @classmethod
    def from_metadata(cls, metadata):
        ret = cls(metadata['programCode'], metadata['programName'])
        return ret

    @classmethod
    def from_json(cls, json_rep):
        product_list = json_rep['programProductList']
        if not product_list:
            return None

        name = product_list[0]['programName']
        code = product_list[0]['programCode']
        products = []
        for p in product_list:
            if p['programName'] != name or p['programCode'] != code:
                raise OpenLMISAPIException('Product list was inconsistent')
            products.append(Product.from_json(p))

        return cls(code=code, name=name, products=products)


def get_facilities(uri_or_text):
    parsed = feedparser.parse(uri_or_text)
    for entry in parsed.entries:
        yield Facility(RssMetadata.from_entry(entry))


def get_facility_programs(uri_or_text):
    parsed = feedparser.parse(uri_or_text)
    for entry in parsed.entries:
        yield FacilityProgramLink(RssMetadata.from_entry(entry))


def get_programs_and_products(uri_or_text):
    parsed = feedparser.parse(uri_or_text)
    for entry in parsed.entries:
        yield Program.from_metadata(RssMetadata.from_entry(entry).metadata)


def get_requisition_statuses(uri_or_text):
    parsed = feedparser.parse(uri_or_text)
    for entry in parsed.entries:
        yield RequisitionStatus(RssMetadata.from_entry(entry))


class OpenLMISEndpoint(object):
    """
    Endpoint for interfacing with the OpenLMIS APIs
    """

    def __init__(self, base_uri, username, password):
        self.base_uri = base_uri.rstrip('/')
        self.username = username
        self.password = password

        # feeds
        self._feed_uri = self._urlcombine(self.base_uri, '/feeds')
        self.facility_master_feed_uri = self._urlcombine(self._feed_uri, '/facilities')
        self.facility_program_feed_uri = self._urlcombine(self._feed_uri, '/programSupported')
        self.program_catalog_feed_uri = self._urlcombine(self._feed_uri, '/programCatalogChanges')
        self.requisition_status_feed_uri = self._urlcombine(self._feed_uri, '/requisition-status')

        # rest apis
        self._rest_uri = self._urlcombine(self.base_uri, '/rest-api')
        self.create_virtual_facility_url = self._urlcombine(self._rest_uri, '/agent.json')
        self.update_virtual_facility_base_url = self._urlcombine(self._rest_uri, '/agent')
        self.program_product_url = self._urlcombine(self._rest_uri, '/programProducts.json')
        self.submit_requisition_url = self._urlcombine(self._rest_uri, '/submitRequisition') #todo waiting for update document, added some url for testing
        self.requisition_details_url = self._urlcombine(self._rest_uri, '/requisitions')
        self.approve_requisition_url = self._urlcombine(self._rest_uri, '/') #todo waiting for update document, added some url for testing
        self.confirm_delivery_base_url = self._urlcombine(self._rest_uri, '/orders')

    def _urlcombine(self, base, target):
        return '{base}{target}'.format(base=base, target=target)

    def _page(self, base, page):
        return '{base}/{page}'.format(base=base, page=page)

    def _iter_feed(self, uri, item_wrapper):
        results = True
        page = 1
        while results:
            next = self._page(uri, page)
            results = list(item_wrapper(next))
            for r in results:
                yield r
            page += 1

    def _auth(self):
        return HTTPBasicAuth(self.username, self.password)

    def _response(self, response):
        # todo: error handling and such
        res = response.json()
        if res.get('Success', False):
            return True
        else:
            raise OpenLMISAPIException(res['error'])

    def get_all_facilities(self):
        return (fac for fac in self._iter_feed(self.facility_master_feed_uri, get_facilities))

    def get_all_requisition_statuses(self):
        return (fac for fac in self._iter_feed(self.requisition_status_feed_uri, get_requisition_statuses))

    def get_all_programs(self, include_products=True):
        programs = (p for p in self._iter_feed(self.program_catalog_feed_uri, get_programs_and_products))
        if include_products:
            return (self.get_program_products(p.code) for p in programs)
        else:
            return programs

    def get_program_products(self, program_code):
        response = requests.get(self.program_product_url, params={'programCode': program_code},
                                auth=self._auth())
        return Program.from_json(response.json())


    def get_requisition_details(self, id):
        response = requests.get(self.update_requisition_details_url(id), auth=self._auth())

        return RequisitionDetails.from_json(response.json())


    def create_virtual_facility(self, facility_data):
        response = requests.post(self.create_virtual_facility_url,
                                 data=json.dumps(facility_data),
                                 headers={'content-type': 'application/json'},
                                 auth=self._auth())
        return self._response(response)

    def update_virtual_facility_url(self, id):
        return self._urlcombine(self.update_virtual_facility_base_url, '/{id}.json'.format(id=id))


    def update_requisition_details_url(self, id):
        return self._urlcombine(self.requisition_details_url, '/{id}.json'.format(id=id))


    def update_virtual_facility(self, id, facility_data):
        facility_data['agentCode'] = id
        response = requests.put(self.update_virtual_facility_url(id),
                                data=json.dumps(facility_data),
                                headers={'content-type': 'application/json'},
                                auth=self._auth())
        return self._response(response)

    def submit_requisition(self, requisition_data):
        response = requests.post(self.submit_requisition_url,
                                 data=json.dumps(requisition_data),
                                 headers={'content-type': 'application/json'},
                                 auth=self._auth())
        return self._response(response)

    def update_confirm_delivery_url(self, order_id):
        return self._urlcombine(self.confirm_delivery_base_url, '/{orderId}/pod.json'.format(orderId=order_id))

    def confirm_delivery(self, order_id, delivery_data):
        response = requests.post(self.update_confirm_delivery_url(order_id),
                                 data=json.dumps(delivery_data),
                                 headers={'content-type': 'application/json'},
                                 auth=self._auth())
        return self._response(response)

    def approve_requisition(self, approve_requisiton):
        response = requests.put(self.approve_requisition_url,
                                headers={'content-type': 'application/json'},
                                auth=self._auth())
        return self._response(response)

    @classmethod
    def from_config(cls, config):
        return cls(config.url, config.username, config.password)


class Requisition(object):

    def __init__(self, agent_code, program_id, products, period_id=None):
        self.agent_code = agent_code
        self.program_id = program_id
        self.period_id = period_id
        self.products = products

    @classmethod
    def from_json(cls, json_rep):
        product_list = json_rep['products']
        if not product_list:
            return None

        agent_code = json_rep['agentCode']
        program_id = json_rep['programId']
        period_id = json_rep['periodId']
        products = []
        for p in product_list:
            products.append(RequisitionProduct.from_json(p))

        return cls(agent_code=agent_code, program_id=program_id, products=products, period_id=period_id)


class RequisitionProduct(Product):

    def __init__(self, code, name=None, description=None, unit=None, category=None, beginning_balance=None,
                 quantity_received=None, quantity_dispensed=None, losses_and_adjustments=None, new_patient_count=None,
                 stock_in_hand=None, stock_out_days=None, quantity_requested=None, reason_for_requested_quantity=None, remarks=None):
        self.beginning_balance = beginning_balance
        self.quantity_received = quantity_received
        self.quantity_dispensed = quantity_dispensed
        self.losses_and_adjustments = losses_and_adjustments
        self.new_patient_count = new_patient_count
        self.stock_in_hand = stock_in_hand
        self.stock_out_days = stock_out_days
        self.quantity_requested = quantity_requested
        self.reason_for_requested_quantity = reason_for_requested_quantity
        self.remarks = remarks
        super(RequisitionProduct, self).__init__(code, name, description, unit, category)

    @classmethod
    def from_json(cls, json_rep):
        code = json_rep['productCode']
        beginning_balance = json_rep.get('beginningBalance', None)
        quantity_received = json_rep.get('quantityReceived', None)
        quantity_dispensed = json_rep.get('quantityDispensed', None)
        losses_and_adjustments = json_rep.get('lossesAndAdjustments', None)
        new_patient_count = json_rep.get('newPatientCount', None)
        stock_in_hand = json_rep.get('stockInHand', None)
        stock_out_days = json_rep.get('stockOutDays', None)
        quantity_requested = json_rep.get('quantityRequested', None)
        reason_for_requested_quantity = json_rep.get('reasonForRequestedQuantity', None)
        remarks = json_rep.get('remarks', None)
        return cls(code=code, beginning_balance=beginning_balance, quantity_received=quantity_received, quantity_dispensed=quantity_dispensed,
                   losses_and_adjustments=losses_and_adjustments, new_patient_count=new_patient_count, stock_in_hand=stock_in_hand, stock_out_days=stock_out_days,
                   quantity_requested=quantity_requested, reason_for_requested_quantity=reason_for_requested_quantity, remarks=remarks)


class RequisitionDetails(Requisition):

    def __init__(self, id, agent_code, program_code, emergency, period_start_date, period_end_date, requisition_status,
                   products, supplying_facility_code=None, order_id=None, order_status=None):

        super(RequisitionDetails, self).__init__(agent_code=agent_code, program_id=program_code, products=products)

        self.id = id
        self.emergency = emergency
        self.period_start_date = period_start_date
        self.period_end_date = period_end_date
        self.requisition_status = requisition_status
        self.order_id = order_id
        self.order_status = order_status
        self.supplying_facility_code = supplying_facility_code

    @classmethod
    def from_json(cls, json_rep):
        json_rep = json_rep["requisition"]
        product_list = json_rep['products']
        if not product_list:
            return None

        id = json_rep['id']
        agent_code = json_rep['agentCode']
        program_code = json_rep['programCode']
        emergency = json_rep['emergency']
        period_start_date = json_rep['periodStartDate']
        period_end_date = json_rep['periodEndDate']
        requisition_status = json_rep['requisitionStatus']
        order_id = json_rep.get('orderId', None)
        order_status = json_rep.get('orderStatus', None)
        supplying_facility_code = json_rep.get('supplyingFacilityCode', None)

        products = []
        for p in product_list:
            products.append(RequisitionProductDetails.from_json(p))

        return cls(id, agent_code, program_code, emergency, period_start_date, period_end_date, requisition_status,
                   products, supplying_facility_code, order_id, order_status)

    def to_requisition_case(self, product_id):
        req_case = RequisitionCase()
        req_case.user_id = self.agent_code
        req_case.set_case_property("program_id", self.program_id)
        req_case.set_case_property("period_id", self.period_id)
        req_case.product_id = product_id
        req_case.external_id = self.id
        req_case.requisition_status = self.requisition_status
        req_case.set_case_property("order_id", self.order_id)
        req_case.set_case_property("order_status", self.order_status)
        req_case.set_case_property("emergency", self.emergency)
        req_case.set_case_property("start_date", self.period_start_date)
        req_case.set_case_peoperty("end_date", self.period_end_date)
        return req_case


class RequisitionProductDetails(RequisitionProduct):

    def __init__(self,  code, beginning_balance,
                 quantity_received, quantity_dispensed=None, losses_and_adjustments=None, new_patient_count=None,
                 stock_in_hand=None, stock_out_days=None, quantity_requested=None, reason_for_requested_quantity=None, remarks=None,
                 total_losses_and_adjustments=None, calculated_order_quantity=None, quantity_approved=None):

        self.total_losses_and_adjustments = total_losses_and_adjustments
        self.calculated_order_quantity = calculated_order_quantity
        self.quantity_approved = quantity_approved

        super(RequisitionProductDetails, self).__init__(code=code, beginning_balance=beginning_balance, quantity_received=quantity_received, quantity_dispensed=quantity_dispensed,
                   losses_and_adjustments=losses_and_adjustments, new_patient_count=new_patient_count, stock_in_hand=stock_in_hand, stock_out_days=stock_out_days,
                   quantity_requested=quantity_requested, reason_for_requested_quantity=reason_for_requested_quantity, remarks=remarks)

    @classmethod
    def from_json(cls, json_rep):
        code = json_rep['productCode']
        beginning_balance = json_rep.get('beginningBalance', None)
        quantity_received = json_rep.get('quantityReceived', None)
        quantity_dispensed = json_rep.get('quantityDispensed', None)
        losses_and_adjustments = json_rep.get('lossesAndAdjustments', None)
        new_patient_count = json_rep.get('newPatientCount', None)
        stock_in_hand = json_rep.get('stockInHand', None)
        stock_out_days = json_rep.get('stockOutDays', None)
        quantity_requested = json_rep.get('quantityRequested', None)
        reason_for_requested_quantity =json_rep.get('reasonForRequestedQuantity', None)
        remarks = json_rep.get('remarks', None)

        total_losses_and_adjustments = json_rep.get('totalLossesAndAdjustments', None)
        calculated_order_quantity = json_rep.get('calculatedOrderQuantity', None)
        quantity_approved = json_rep.get('quantityApproved', None)

        return cls(code=code, beginning_balance=beginning_balance,
                 quantity_received=quantity_received, quantity_dispensed=quantity_dispensed, losses_and_adjustments=losses_and_adjustments, new_patient_count=new_patient_count,
                 stock_in_hand=stock_in_hand, stock_out_days=stock_out_days, quantity_requested=quantity_requested, reason_for_requested_quantity=reason_for_requested_quantity, remarks=remarks,
                 total_losses_and_adjustments=total_losses_and_adjustments, calculated_order_quantity=calculated_order_quantity, quantity_approved=quantity_approved)
