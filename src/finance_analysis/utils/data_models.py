from typing import Literal, Dict, Any
from pydantic import BaseModel, Field, field_validator, model_validator
from finance_analysis.config.config import invoice_list

# Define a Literal type for the 30 valid currency codes
CurrencyCodeLiteral = Literal[
    "AUD",
    "BGN",
    "BRL",
    "CAD",
    "CHF",
    "CNY",
    "CZK",
    "DKK",
    "GBP",
    "HKD",
    "HUF",
    "IDR",
    "ILS",
    "INR",
    "ISK",
    "JPY",
    "KRW",
    "MXN",
    "MYR",
    "NOK",
    "NZD",
    "PHP",
    "PLN",
    "RON",
    "SEK",
    "SGD",
    "THB",
    "TRY",
    "USD",
    "ZAR",
    "EUR",
]

InvoiceTypeLiteral = Literal[tuple(invoice_list["types"].keys())]


class CurrencyConversionOutput(BaseModel):
    EUR_Amount: float
    Exchange_Rate_Date: str


class OutputStructure(BaseModel):
    total_amount: str = Field(
        ...,
        description="The total amount on the invoice. Use the format as 1234.56, 400.00, etc.",
        examples=["1234.56", "400.00"],
    )
    currency: str = Field(
        ...,
        description="The currency of the invoice. Example: EUR, USD, etc.",
        examples=["EUR", "USD"],
    )
    issue_date: str = Field(
        ...,
        description="The issue date of the invoice. Use the date format as DD.MM.YYYY",
    )
    description: str = Field(
        ...,
        description="A very short description of the invoice. For example: Hotel Four Seasons, Taxi from airport to hotel, Flight to Paris, etc.",
        examples=[
            "Hotel Four Seasons",
            "Taxi from airport to hotel",
            "Flight to Paris",
        ],
    )


class HotelOutputStructure(BaseModel):
    guest_name: str = Field(
        ...,
        description="The name of the guest in the hotel invoice. Use the format as 'FirstName LastName'.",
        examples=["John Doe", "Jane Smith"],
    )
    total_amount: str = Field(
        ...,
        description="The total amount on the invoice. Use the format as 1234.56, 400.00, etc.",
        examples=["1234.56", "400.00"],
    )
    currency: str = Field(
        ...,
        description="The base currency of the invoice. Example: EUR, USD, etc.",
        examples=["EUR", "USD"],
    )
    checkin_date: str = Field(
        ...,
        description="The arrival / check-in date of the guest. Use the date format as DD.MM.YYYY",
    )
    checkout_date: str = Field(
        ...,
        description="The check-out date of the guest, i.e. when he/she left. Use the date format as DD.MM.YYYY",
    )
    description: str = Field(
        ...,
        description="A very short description of the invoice. For example: Hotel Four Seasons, Taxi from airport to hotel, Flight to Paris, etc.",
        examples=[
            "Hotel Four Seasons",
            "Taxi from airport to hotel",
            "Flight to Paris",
        ],
    )


class ClassifierOutput(BaseModel):
    """
    OutputStructure is a Pydantic model that defines the structure of the output for an invoice type classification.

    Attributes:
        invoice_type (Literal): The type of the invoice, which is restricted to the keys of the "types" dictionary
            in the `invoice_list`. The description includes a list of possible keys.
        class_probs (dict): A dictionary containing the probabilities of each detected invoice type.
        reasoning (str): A string explaining the reasoning behind the classification decision.
    """

    invoice_type: InvoiceTypeLiteral = Field(
        description=f"Language of the input text out of the following key-value list of {list(invoice_list['types'].keys())}"
    )
    class_probs: dict = Field(
        default_factory=lambda: {"unknown": 1.0},
        description="Probabilities of the detected invoice type. The keys are the types of invoices, and the values are their respective probabilities. The probabilities should sum to 1.",
        examples=[
            {
                "invoice_type_1": 0.8,
                "invoice_type_2": 0.2,
            }
        ],
    )
    reasoning: str = Field(
        default="Classification failed or returned invalid format",
        description="The reasoning behind the classification decision. This should explain why the model classified the invoice as a certain type.",
        examples=[
            "The invoice contains the word 'hotel' and mentions a guest's name, indicating it is a hotel invoice."
        ],
    )

    @field_validator("invoice_type")
    @classmethod
    def validate_invoice_type(cls, v) -> str:
        """Validate and provide fallback for invoice_type"""
        if (
            v is None or v not in invoice_list["types"].keys()
        ):  # v: field being validated
            return "unknown"
        return v

    @field_validator("class_probs")
    @classmethod
    def validate_class_probs(cls, v):
        """Ensure class_probs is a valid dict"""
        if not isinstance(v, dict) or not v:
            return {"unknown": 1.0}
        return v

    @model_validator(mode="after")
    def ensure_consistency(self):
        """Ensure invoice_type matches the highest probability in class_probs"""
        if self.invoice_type not in self.class_probs:
            self.class_probs[self.invoice_type] = (
                max(self.class_probs.values()) if self.class_probs else 1.0
            )
        return self


class TripMetadata(BaseModel):
    last_first_name: str = Field(
        description="The last and first name of the traveler in the format 'Last, First'.",
        default="Vosseler, Alexander",
    )
    location: str = Field(
        description="The traveler's home location or base city.", default="Munich"
    )
    destination: str = Field(
        description="The destination of the trip.", default="Barcelona"
    )
    cost_center: str = Field(
        description="The cost center associated with the trip.", default="100392"
    )
    reason_for_travel: str = Field(
        description="The reason for the travel.", default="Workshop"
    )


class XlsOutputArgs(BaseModel):
    trip_metadata: TripMetadata = TripMetadata()
    dir_name: str = Field(
        description="The directory where the input file is located.",
        default="/Users/avosseler/Business Trips/2025/tmp",
    )
    input_file: str = Field(
        description="The input file name, typically a merged PDF of all invoices.",
        default="Travel Expense Tmp.xlsx",
    )
    output_file: str = Field(
        description="The desired output Excel file name.",
        default="my_travel_expenses.xlsx",
    )

    def to_xlsx_format(self) -> Dict[str, Any]:
        """Convert to the exact format expected by update_travel_expense_xlsx"""
        return {
            "trip_metadata": {
                "Last/First name": self.trip_metadata.last_first_name,
                "Location": self.trip_metadata.location,
                "Destination": self.trip_metadata.destination,
                "Cost Center": self.trip_metadata.cost_center,
                "Reason for travel": self.trip_metadata.reason_for_travel,
            },
            "dir_name": self.dir_name,
            "input_file": self.input_file,
            "output_file": self.output_file,
        }
