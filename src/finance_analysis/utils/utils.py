import os
import requests
from typing import Optional, List, Dict, Any
from datetime import datetime
from PyPDF2 import PdfMerger
from openpyxl import load_workbook
from openpyxl.workbook.properties import CalcProperties
from finance_analysis.utils.data_models import (
    CurrencyCodeLiteral,
    CurrencyConversionOutput,
)
from finance_analysis.services.logger import LoggerFactory

my_logger = LoggerFactory(handler_type="Stream").create_module_logger()


def convert_currency(
    amount: float,
    from_currency: CurrencyCodeLiteral,
) -> CurrencyConversionOutput:
    """
    Convert a monetary amount from one currency to another via api.frankfurter.app

    Args:
        amount (float): Input amount to convert
        from_currency (CurrencyCodeLiteral): Abbreviation of the currency to convert from, e.g. "USD"

    Returns:
        Dict[str, float]: A dictionary containing the converted amount and the date of conversion
    """
    if from_currency == "EUR":
        return {"EUR Amount": amount, "Exchange Rate - Date": "Not Applicable"}

    # If currency is not Euro, convert to Euro:
    resp = requests.get(
        "https://api.frankfurter.app/latest",
        params={"amount": f"{amount}", "from": f"{from_currency.upper()}", "to": "EUR"},
        timeout=10,
        verify=False,
    )
    resp.raise_for_status()
    euro_amount = resp.json()["rates"].get("EUR")  # Converted amount in EUR
    date = resp.json()["date"]
    return {"EUR Amount": euro_amount, "Exchange Rate - Date": date}


def create_conversion_info(result: dict) -> str:
    """
    Create a conversion info string based on the provided result.

    Args:
        result (dict): The result dictionary containing entities.

    Returns:
        str: A formatted string with conversion information.
    """
    # Assuming the first entity contains the currency
    if not result["entities"]:
        return "No entities found."

    # Extracting the base currency from the first entity
    base_currencies = list(set(result["currencies"]))
    non_euro = [c for c in base_currencies if c != "EUR"]
    if len(non_euro) == 0:
        print("No non-Euro currencies found.")
        base_currency = "EUR"  # Default to Euro if no other currency is found
    else:
        base_currency = non_euro[0]  # Use the first non-Euro currency
        print(f"Using {base_currency} as the base currency for conversion.")

    info = convert_currency(amount=1, from_currency=base_currency)

    valid_date = datetime.now().strftime("%d.%m.%y")
    rate_info = f"Daily exchange rate: 1 {base_currency} = {info['EUR Amount']} Euro (as of {valid_date})"
    return rate_info


def merge_pdfs(
    pdf_dir: str,
    pdf_names: Optional[List[str]] = None,
    first_file: Optional[str] = None,
    output_file: str = "merged_files.pdf",
) -> None:
    """
    Merges multiple PDF files from a specified directory into a single PDF file.

    Args:
        pdf_dir (str): The directory containing the PDF files to merge.
        pdf_names (List[str]): List of PDF file names (with extension) that must be present in the directory.
        first_file (Optional[str], optional): The PDF file to be placed first in the merged output. Defaults to None.
        output_file (str, optional): The name of the output merged PDF file. Defaults to "merged_files.pdf".
    """

    all_files = os.listdir(pdf_dir)
    if pdf_names is None:
        pdf_names = [f for f in all_files if f.endswith(".pdf")]

    # Check if all pdf_names are present in directory
    missing = [f for f in pdf_names if f not in all_files]
    if missing:
        raise FileNotFoundError(
            f"The following files are missing in {pdf_dir}: {missing}"
        )

    merger = PdfMerger()

    if first_file:
        merger.merge(0, os.path.join(pdf_dir, first_file))
        print(f"Adding {first_file}...")

    for page_number, file in enumerate(pdf_names, start=1):
        if file.endswith(".pdf") and file != first_file:
            print(f"Appending {file}...")
            merger.merge(page_number, os.path.join(pdf_dir, file))

    merger.write(os.path.join(pdf_dir, output_file))
    merger.close()
    my_logger.info(f"Merged PDF created as {os.path.join(pdf_dir, output_file)}")


def update_travel_expense_xlsx(
    result: Dict[str, Any],
    trip_metadata: Dict[str, str] = {
        "Last/First name": "Vosseler, Alexander",
        "Location": "Munich",
        "Destination": "Barcelona",
        "Cost Center": "100392",
        "Reason for travel": "Workshop",
    },
    dir_name: str = "/Users/avosseler/Business Trips/2025/tmp",
    input_file: str = "Travel Expense Tmp.xlsx",
    output_file: str = "Travel Expense Tmp Edt.xlsx",
) -> None:
    """
    Update the travel expense Excel file with extracted invoice data.

    Args:
        result (dict): The result dictionary containing invoice entities.
        dir_name (str): Directory containing the Excel file.
        input_file (str): Name of the input Excel file.
        output_file (str): Name of the output Excel file.
        sheet_name (str): Name of the worksheet to update.
    """
    pfile = os.path.join(dir_name, input_file)
    if not os.path.exists(pfile):
        raise FileNotFoundError(f"Input file {pfile} does not exist.")
    my_logger.info(f"Updating travel expense file: {pfile}")
    wb = load_workbook(pfile, data_only=False)
    ws = wb["RKA Seite 1"]

    # --------------------------- Sheet 1 ------------------------------------
    # Overwrite the cells that feed into formulas
    ws["C2"] = trip_metadata.get("Last/First name", "Vosseler, Alexander")
    ws["E2"] = trip_metadata.get("Cost Center", "100392")  # cost center
    ws["E3"] = trip_metadata.get("Location", "Munich")  # location
    ws["C6"] = trip_metadata.get("Destination", "Barcelona")  # destination
    ws["C7"] = trip_metadata.get("Reason for travel", "Workshop")  # Reason for travel

    rowA = 19
    entries = 1
    rowB = 29
    for res in result["entities"]:
        if res["invoice_type"] == "hotel":
            ws[f"A{rowA}"] = res["checkin_date"]
            ws[f"B{rowA}"] = entries
            ws[f"C{rowA}"] = res["description"]
            ws[f"E{rowA}"] = res["total_amount"]
            rowA += 1
        else:
            ws[f"A{rowB}"] = res["issue_date"]
            ws[f"B{rowB}"] = entries
            ws[f"C{rowB}"] = res["description"]
            ws[f"E{rowB}"] = res["total_amount"]
            rowB += 1
        entries += 1

    ws[f"C{rowB+2}"] = result["rate_info"]  # Add exchange rate info

    # --------------------------- Sheet 2 ------------------------------------
    ws2 = wb["RKA Seite 2"]

    # Manually attach CalcProperties to force full recalc on load
    wb._calculation_properties = CalcProperties(fullCalcOnLoad=True)

    # Save to a new file (or overwrite)
    wb.save(os.path.join(dir_name, output_file))
    my_logger.info(
        f"Updated travel expense file saved as: {os.path.join(dir_name, output_file)}"
    )
