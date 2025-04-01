from dataclasses import dataclass
from typing import Literal


@dataclass
class PartyDetails:
    partyIdType: Literal["MSISDN", "EMAIL"]
    partyId: str


@dataclass
class PaymentTransferDetails:
    amount: str
    currency: str
    externalId: str
    payerMessage: str
    payeeNote: str
    payee: PartyDetails
