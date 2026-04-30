from dataclasses import dataclass
from typing import Literal


@dataclass
class PartyDetails:
    partyIdType: Literal["MSISDN", "EMAIL"]
    partyId: str


@dataclass
class MTNPaymentTransferDetails:
    amount: str
    currency: str
    externalId: str
    payerMessage: str
    payeeNote: str
    payee: PartyDetails


@dataclass
class OrangeCameroonPaymentTransferDetails:
    channelUserMsisdn: str
    pin: str
    amount: str
    subscriberMsisdn: str
    orderId: str
    description: str
