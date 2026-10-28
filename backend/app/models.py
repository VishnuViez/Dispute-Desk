"""
models.py – Shared Pydantic response models.

Field descriptions are written for a non-expert reader because
IBM watsonx Orchestrate uses them to understand what each field means.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str = Field(description="Always 'ok' when the API is running.")
    database: str = Field(
        description="'connected' if the database file is present, 'missing' if not."
    )


# ---------------------------------------------------------------------------
# GET /tools/disputes/{dispute_id}
# ---------------------------------------------------------------------------

class DisputeResponse(BaseModel):
    dispute_id: str = Field(description="Unique identifier for this dispute (e.g. DSP-0001).")
    transaction_id: str = Field(description="The transaction the customer is disputing.")
    customer_id: str = Field(description="The customer who filed the dispute.")
    filed_date: str = Field(description="Date the customer filed the dispute (YYYY-MM-DD).")
    complaint_text: str = Field(description="The customer's complaint in their own words.")
    status: str = Field(
        description="Current status: 'open', 'resolved_customer', 'resolved_merchant', or 'withdrawn'."
    )
    card_type: str = Field(
        description="Whether the disputed charge was on a credit or debit card."
    )


# ---------------------------------------------------------------------------
# GET /tools/transactions/{transaction_id}
# ---------------------------------------------------------------------------

class RefundRecord(BaseModel):
    refund_id: str = Field(description="Unique identifier for this refund.")
    refund_date: str = Field(description="Date the refund was processed (YYYY-MM-DD).")
    amount_usd: float = Field(description="Amount refunded in US dollars.")


class PossibleDuplicate(BaseModel):
    transaction_id: str = Field(description="ID of the other charge that looks like a duplicate.")
    txn_datetime: str = Field(description="Date and time of the other charge.")
    minutes_apart: float = Field(
        description="How many minutes separated this charge from the disputed one."
    )


class TransactionResponse(BaseModel):
    transaction_id: str = Field(description="Unique identifier for this transaction (e.g. TXN-000001).")
    card_id: str = Field(description="The card that was charged.")
    customer_id: str = Field(description="The customer who owns the card.")
    merchant_id: str = Field(description="The merchant that processed the charge.")
    merchant_name: str = Field(description="Plain-English name of the merchant.")
    merchant_category: str = Field(description="Type of business (e.g. coffee_shop, online_retail).")
    txn_datetime: str = Field(description="Date and time the transaction occurred.")
    amount_usd: float = Field(description="Charge amount in US dollars.")
    currency: str = Field(description="Currency of the charge (always USD in this prototype).")
    channel: str = Field(description="How the charge was made: 'in_store', 'online', or 'recurring'.")
    device_id: str | None = Field(
        description="Device used for online purchases. Null for in-store charges."
    )
    shipping_address_id: str | None = Field(
        description="Shipping address for online orders of physical goods. Null otherwise."
    )
    subscription_id: str | None = Field(
        description="Subscription this charge belongs to, if it is a recurring charge."
    )
    subscription_start_date: str | None = Field(
        description="Date the subscription started. Null if not a recurring charge."
    )
    subscription_cancelled_date: str | None = Field(
        description="Date the subscription was cancelled, or null if it is still active."
    )
    statement_date: str = Field(
        description="Date of the first card statement that showed this charge."
    )
    status: str = Field(description="'posted' or 'refunded'.")
    card_type: str = Field(description="'credit' or 'debit'.")
    refunds: list[RefundRecord] = Field(
        description="Any refunds that have been applied to this transaction."
    )
    possible_duplicates: list[PossibleDuplicate] = Field(
        description=(
            "Other charges on the same card at the same merchant for the same amount "
            "within 24 hours. An empty list means no duplicates were found."
        )
    )


# ---------------------------------------------------------------------------
# GET /tools/customers/{customer_id}/history
# ---------------------------------------------------------------------------

class TransactionSummary(BaseModel):
    transaction_id: str = Field(description="Unique transaction identifier.")
    merchant_id: str = Field(description="Merchant that received the payment.")
    merchant_name: str = Field(description="Plain-English name of the merchant.")
    txn_datetime: str = Field(description="Date and time of the transaction.")
    amount_usd: float = Field(description="Amount charged in US dollars.")
    channel: str = Field(description="'in_store', 'online', or 'recurring'.")
    device_id: str | None = Field(description="Device used for online purchases.")
    shipping_address_id: str | None = Field(description="Shipping address for physical goods orders.")


class FraudSignals(BaseModel):
    prior_undisputed_with_merchant: int = Field(
        description=(
            "Number of earlier charges at the same merchant that were never disputed. "
            "A high count can indicate the customer knows the merchant well."
        )
    )
    same_device_count: int = Field(
        description=(
            "Among those prior purchases at the same merchant, how many used the same "
            "device as the charge being investigated."
        )
    )
    same_address_count: int = Field(
        description=(
            "Among those prior purchases at the same merchant, how many were shipped to "
            "the same address as the charge being investigated."
        )
    )
    device_seen_before: bool = Field(
        description=(
            "True if the device used for the disputed charge appeared in any earlier "
            "transaction by this customer, not just with this merchant."
        )
    )
    address_seen_before: bool = Field(
        description=(
            "True if the shipping address on the disputed charge appeared in any earlier "
            "transaction by this customer, not just with this merchant."
        )
    )
    prior_disputes_count: int = Field(
        description="Total number of past disputes (any status) filed by this customer."
    )
    prior_disputes_lost: int = Field(
        description=(
            "Number of past disputes where the outcome was resolved_merchant "
            "(the merchant won). A high number alongside other signals may warrant closer review."
        )
    )
    summary: str = Field(
        description="One plain-English sentence summarising the key facts above."
    )


class CustomerHistoryResponse(BaseModel):
    customer_id: str = Field(description="The customer whose history is shown.")
    account_open_date: str = Field(description="Date the customer opened their account.")
    transactions: list[TransactionSummary] = Field(
        description="Up to 50 of the customer's most recent transactions, newest first."
    )
    friendly_fraud_signals: FraudSignals | None = Field(
        default=None,
        description=(
            "Populated only when both merchant_id and transaction_id query parameters "
            "are provided. Contains evidence relevant to assessing whether the dispute "
            "may be a familiar purchase the customer later denied."
        ),
    )


# ---------------------------------------------------------------------------
# GET /tools/merchants/{merchant_id}
# ---------------------------------------------------------------------------

class ShipmentRecord(BaseModel):
    shipment_id: str = Field(description="Unique identifier for this shipment.")
    carrier: str = Field(description="Shipping carrier (e.g. FedEx, UPS).")
    shipped_date: str | None = Field(description="Date the item was shipped, or null if not yet shipped.")
    expected_delivery_date: str = Field(description="Date the item was expected to arrive.")
    delivered_date: str | None = Field(description="Actual delivery date, or null if not yet delivered.")
    delivery_status: str = Field(
        description="Current status: 'delivered', 'in_transit', 'lost', or 'not_shipped'."
    )
    proof_of_delivery: bool = Field(
        description="True if the carrier recorded proof of delivery (e.g. a signature or photo)."
    )


class MerchantResponse(BaseModel):
    merchant_id: str = Field(description="Unique merchant identifier (e.g. MERCH-001).")
    name: str = Field(description="Merchant's trading name.")
    category: str = Field(
        description="Type of business (coffee_shop, restaurant, grocery, online_retail, electronics, streaming, fitness, or travel)."
    )
    is_online: bool = Field(description="True if this merchant operates online.")
    refund_policy: str = Field(description="The merchant's stated refund policy.")
    shipment: ShipmentRecord | None = Field(
        default=None,
        description=(
            "Shipment information for the provided transaction_id. "
            "Null if no shipment record exists or no transaction_id was given."
        ),
    )
