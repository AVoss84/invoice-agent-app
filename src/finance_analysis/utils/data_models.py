from typing import Literal
from pydantic import BaseModel, Field
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

    # invoice_text: str = Field(description="Input text of the invoice")
    invoice_type: Literal[tuple(invoice_list["types"].keys())] = Field(
        description=f"Language of the input text out of the following key-value list of {list(invoice_list["types"].keys())}"
    )
    class_probs: dict = Field(
        description="Probabilities of the detected invoice type. The keys are the types of invoices, and the values are their respective probabilities. The probabilities should sum to 1.",
        examples=[
            {
                "invoice_type_1": 0.8,
                "invoice_type_2": 0.2,
            }
        ],
    )
    reasoning: str = Field(
        description="The reasoning behind the classification decision. This should explain why the model classified the invoice as a certain type.",
        examples=[
            "The invoice contains the word 'hotel' and mentions a guest's name, indicating it is a hotel invoice."
        ],
    )
