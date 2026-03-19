import os
import re
import base64
import mimetypes
from typing import TypedDict, Annotated, List, Dict, Literal, Any, get_args
from operator import add
from langgraph.graph import StateGraph, START, END
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command
from langchain_core.messages import HumanMessage
from finance_analysis.resources.extractor import EntityExtractor
from finance_analysis.resources.document_processor import DocumentProcessor_GCP

# from finance_analysis.resources.document_processor import DocumentProcessor
from finance_analysis.resources.invoice_classifier import InvoiceDetector
from finance_analysis.services.logger import LoggerFactory
from langchain_core.prompts import PromptTemplate
from finance_analysis.resources.get_models import InitModels
from finance_analysis.config import global_config as glob
from finance_analysis.utils.prompts import summary_prompt
from finance_analysis.utils.utils import (
    convert_currency,
    create_conversion_info,
    update_travel_expense_xlsx,
    retry,
)
from finance_analysis.utils.data_models import (
    XlsOutputArgs,
    CurrencyCodeLiteral,
    OutputStructure,
    HotelOutputStructure,
    DirectInvoiceOutput,
    InvoiceTypeWithUnknownLiteral,
)

my_logger = LoggerFactory().create_module_logger()

GeminiPart = dict[str, Any]
ExtractedFields = dict[str, str | float | None]
GraphResult = dict[str, Any]


class DocState(TypedDict):
    file_names: list[str]  # List of files to process
    current_file_index: int  # Index of the current file
    file_name: str  # Name of the current file
    processed_doc: str
    invoice_type: str
    entities: Annotated[list[dict[str, str]], add]
    inferred_types: Annotated[list[str], add]  # collect all inferred types
    currencies: Annotated[list[CurrencyCodeLiteral], add]  # collect all currencies
    descriptions: Annotated[list[str], add]  # describe each invoice, Hotel Name, etc.
    summary: str  # Summary of the processed documents
    rate_info: str  # Information about exchange rates
    direct_extracted: dict[str, Any]


class ProcessorGraph:
    """
    ProcessorGraph class orchestrates the document processing workflow,
    including loading files, processing documents, classifying invoices,
    and extracting entities.
    """

    processor_graph: CompiledStateGraph
    initial_state: GraphResult

    def __init__(
        self,
        list_of_files: list[str],
        xls_output_file_args: XlsOutputArgs | None = None,
    ) -> None:
        """
        Initialize the document-processing workflow and compiled graph.

        Args:
            list_of_files: Absolute paths to the invoice files to process.
            xls_output_file_args: Optional Excel output configuration. When not
                provided, the defaults from `XlsOutputArgs` are used.
        """
        self.initial_state = {
            "file_names": list_of_files,
            "current_file_index": 0,
            "entities": [],
            "inferred_types": [],
        }
        models = InitModels()
        self.llm = models.llm
        self.ocr_mode = glob.OCR_MODE.lower()
        if xls_output_file_args is None:
            xls_output_file_args = XlsOutputArgs()
        self.input_args: Dict[str, str] = xls_output_file_args.to_xlsx_format()
        self.processor_graph: CompiledStateGraph = self._initialize_graph()
        my_logger.info(
            f"🤖 Supervisor initialized with {len(list_of_files)} files to process."
        )

    @staticmethod
    def load_next_file(
        state: DocState,
    ) -> Command[Literal["process", "summarize"]]:
        """
        Loads the next file from the list in the state.
        Advances the current file index and updates the state.

        Args:
            state (DocState): The current processing state.

        Returns:
            Command: The next command to execute in the workflow.
        """
        index: int = state.get("current_file_index", 0)
        file_list: List[str] = state.get("file_names", [])

        my_logger.info(f"🔄 Loading next file - Index: {index}/{len(file_list)}")

        # Finally: Goto Summarization if no more files
        if index >= len(file_list):
            my_logger.info("All files processed, moving to summarization...")
            return Command[Literal["process", "summarize"]](goto="summarize")

        base_name = os.path.basename(file_list[index])

        my_logger.info(f"📁 Loading file: {base_name}")
        return Command[Literal["process", "summarize"]](
            update={"file_name": file_list[index]},  # Don't increment here!
            goto="process",
        )
        # # Finally: Goto Summarization if no more files
        # if index >= len(file_list):
        #     return Command(goto="summarize")

        # print(f"\nLoading file: {file_list[index]}")
        # return Command(
        #     update={"file_name": file_list[index], "current_file_index": index + 1},
        #     goto="process",  # next step (-> edge)
        # )

    def process_document(
        self, state: DocState
    ) -> Command[Literal["extract", "classify"]]:
        """
        Processes the current document by reading and converting it to markdown.

        Args:
            state (DocState): The current processing state.

        Returns:
            Command: The next command to execute in the workflow.
        """
        base_name = os.path.basename(state["file_name"])
        my_logger.info(f"📋 Processing file: {base_name}")

        if self.ocr_mode == "gemini_direct":
            my_logger.info("🤖 Using Gemini direct multimodal mode")
            extracted = self._extract_with_gemini_direct(state["file_name"])
            inferred_type = str(extracted.get("invoice_type", "unknown") or "unknown")
            return Command(
                update={
                    "processed_doc": "",
                    "invoice_type": inferred_type,
                    "inferred_types": [inferred_type],
                    "direct_extracted": extracted,
                },
                goto="extract",
            )

        dproc = DocumentProcessor_GCP(
            file_path=state["file_name"],
            project_id="neme-ai-rnd-dev-prj-01",
            location="eu",
            processor_id="c48f6c912b9ff9d5",
        )

        # dproc = DocumentProcessor(file_path=state["file_name"])
        dproc.process()
        processed = dproc.to_markdown()
        my_logger.info(f"🧾 OCR output for {base_name}:\n{processed}")
        return Command(update={"processed_doc": processed}, goto="classify")

    @staticmethod
    def _file_to_gemini_part(file_path: str) -> GeminiPart:
        """
        Convert a local PDF or image file into a Gemini multimodal message part.

        Args:
            file_path: Absolute path to the source file.

        Returns:
            A message part compatible with the Gemini multimodal API.
        """
        mime_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
        with open(file_path, "rb") as input_file:
            file_bytes = input_file.read()

        if mime_type.startswith("image/"):
            encoded = base64.b64encode(file_bytes).decode("utf-8")
            return {
                "type": "image_url",
                "image_url": {"url": f"data:{mime_type};base64,{encoded}"},
            }

        return {"type": "media", "mime_type": mime_type, "data": file_bytes}

    def _extract_with_gemini_direct(self, file_path: str) -> ExtractedFields:
        """
        Run a single Gemini multimodal call to classify and extract invoice data.

        Args:
            file_path: Absolute path to the source invoice document.

        Returns:
            A normalized dictionary representation of `DirectInvoiceOutput`.
        """
        structured_llm = self.llm.with_structured_output(DirectInvoiceOutput)
        _valid_types = ", ".join(get_args(InvoiceTypeWithUnknownLiteral))
        _f = OutputStructure.model_fields
        _fh = HotelOutputStructure.model_fields
        prompt_text = (
            "Classify this document and extract all invoice fields.\n"
            f"invoice_type must be one of: {_valid_types}.\n"
            f"total_amount — {_f['total_amount'].description}\n"
            f"currency — {_f['currency'].description}\n"
            f"issue_date — {_f['issue_date'].description}\n"
            f"checkin_date — {_fh['checkin_date'].description}\n"
            f"checkout_date — {_fh['checkout_date'].description}\n"
            f"guest_name — {_fh['guest_name'].description}\n"
            f"description — {_f['description'].description}\n"
            "Use null for any field that is not present in the document."
        )
        response = structured_llm.invoke(
            [
                HumanMessage(
                    content=[
                        self._file_to_gemini_part(file_path),
                        {"type": "text", "text": prompt_text},
                    ]
                )
            ]
        )
        if hasattr(response, "model_dump"):
            return response.model_dump()
        return response

    @staticmethod
    @retry(attempts=3)
    async def _extract_entities(
        invoice_type: str, processed_doc: str
    ) -> ExtractedFields:
        """
        Extract invoice fields from OCR text using the type-specific extractor.

        Args:
            invoice_type: Classified invoice type used to select the prompt.
            processed_doc: OCR text content passed to the extractor.

        Returns:
            Extracted invoice fields as a dictionary.

        Raises:
            ValueError: If the extractor omits required fields.
        """
        extractor = EntityExtractor(invoice_type)
        extracted = await extractor.aextract_entities(processed_doc)

        # Validate that we got the expected fields
        required_fields = ["total_amount", "currency"]
        for field in required_fields:
            if field not in extracted:
                raise ValueError(
                    f"Missing required field '{field}' in extraction result"
                )

        return extracted

    @staticmethod
    def _normalize_extracted_fields(extracted: dict[str, Any]) -> ExtractedFields:
        """
        Normalize heterogeneous extractor keys into the shared invoice schema.

        Args:
            extracted: Raw extraction output from Gemini or the OCR-based extractor.

        Returns:
            A dictionary using the shared field names expected downstream.
        """
        if not isinstance(extracted, dict):
            return {}

        def _get_first(*keys: str) -> str | float | None:
            for key in keys:
                if key in extracted and extracted[key] not in (None, ""):
                    return extracted[key]
            return None

        normalized = dict(extracted)
        normalized["total_amount"] = _get_first(
            "total_amount", "amount", "invoice_total", "total", "gesamtbetrag"
        )
        normalized["currency"] = (
            _get_first("currency", "curr", "invoice_currency", "waehrung", "wahrung")
            or "EUR"
        )
        normalized["issue_date"] = _get_first(
            "issue_date", "invoice_date", "date", "datum"
        )
        normalized["checkin_date"] = _get_first(
            "checkin_date", "arrival_date", "check_in_date"
        )
        normalized["checkout_date"] = _get_first(
            "checkout_date", "departure_date", "check_out_date"
        )
        return normalized

    @staticmethod
    def _parse_amount(value: object) -> float:
        """
        Parse localized amount strings into a float.

        Args:
            value: Raw amount value returned by the extractor.

        Returns:
            The parsed numeric amount.

        Raises:
            ValueError: If the amount is missing or cannot be parsed.
        """
        if isinstance(value, (int, float)):
            return float(value)

        if value is None:
            raise ValueError("Missing total_amount")

        amount_str = str(value).strip()
        if not amount_str:
            raise ValueError("Missing total_amount")

        amount_str = re.sub(r"[^0-9,.-]", "", amount_str)
        if not amount_str:
            raise ValueError("Invalid total_amount")

        has_dot = "." in amount_str
        has_comma = "," in amount_str

        if has_dot and has_comma:
            if amount_str.rfind(",") > amount_str.rfind("."):
                amount_str = amount_str.replace(".", "").replace(",", ".")
            else:
                amount_str = amount_str.replace(",", "")
        elif has_comma:
            amount_str = amount_str.replace(",", ".")

        return float(amount_str)

    @staticmethod
    async def extract_and_convert(state: DocState) -> Command[Literal["load"]]:
        """
        Extracts entities from the provided document state, converts the extracted amount to EUR, and prepares an update command.

        This static asynchronous method performs the following steps:
        1. Extracts raw entities from the processed document using the appropriate entity extractor based on the invoice type.
        2. Converts the extracted total amount from its original currency to EUR.
        3. Updates the extracted entities with the converted amount and sets the currency to EUR.
        4. Increments the current file index to process the next document.
        5. Returns a Command object containing the updated entities, conversion result, currency list, descriptions, and the incremented file index, directing the workflow to the "load" state.

        If an exception occurs during extraction or conversion:
        - Logs the error.
        - Increments the file index to skip the problematic file.
        - Returns a Command object with a default entity indicating extraction failure, and updates the workflow to the "load" state.

        Args:
            state (DocState): The current document state containing information such as invoice type, processed document, and file index.

        Returns:
            Command: An object containing updates to the state and the next workflow step.
        """

        try:
            # 1) pull raw entities from doc using retry decorator or direct multimodal extraction
            if state.get("direct_extracted"):
                raw_extracted = state["direct_extracted"]
            else:
                raw_extracted = await ProcessorGraph._extract_entities(
                    state["invoice_type"], state["processed_doc"]
                )
            extracted = ProcessorGraph._normalize_extracted_fields(raw_extracted)

            # 2) convert immediately
            amount_raw = extracted.get("total_amount")
            from_cur = str(extracted.get("currency", "EUR") or "EUR").strip().upper()
            try:
                amount = ProcessorGraph._parse_amount(amount_raw)
            except ValueError:
                amount = 0.0

            print(f"Converting {amount} {from_cur} to EUR...")
            conv = convert_currency(amount, from_cur)
            print(f"💰 Converted amount: {conv['EUR Amount']} EUR")

            extracted["total_amount"] = conv["EUR Amount"]
            extracted["currency"] = "EUR"
            extracted["invoice_type"] = state.get("invoice_type", "unknown")

            # Increment index after successful processing
            current_index: int = state.get("current_file_index", 0)

            # 3) stash both original + conversion, then loop back
            return Command(
                update={
                    "entities": [extracted],
                    "conversion_result": conv,
                    "currencies": [
                        from_cur
                    ],  # must be list for concatenation, as you use the 'add' operator above
                    "descriptions": [
                        extracted.get("description", "No description provided")
                    ],
                    "current_file_index": current_index + 1,  # Increment here!
                },
                goto="load",
            )

        except Exception as e:
            my_logger.error(f"❌ Entity extraction failed: {str(e)}")
            # Still increment to skip the problematic file
            current_index = state.get("current_file_index", 0)
            default_entity = {
                "total_amount": "0.00",
                "currency": "EUR",
                "description": f"Failed to extract from: {state.get('file_name', 'unknown')}",
                "issue_date": "N/A",
                "invoice_type": state.get("invoice_type", "unknown"),
            }

            return Command(
                update={
                    "entities": [default_entity],
                    "currencies": ["EUR"],
                    "descriptions": [
                        f"Failed to extract from: {state.get('file_name', 'unknown')}"
                    ],
                    "current_file_index": current_index
                    + 1,  # Increment even on failure
                },
                goto="load",
            )

    @staticmethod
    @retry(attempts=3)
    async def _classify_document(processed_doc: str) -> dict[str, Any]:
        """
        Classify a processed document to determine its invoice type.

        This function uses an InvoiceDetector to asynchronously analyze the input text
        and classify the type of invoice document.

        Args:
            processed_doc (str): The preprocessed document text to be classified.

        Returns:
            dict: A dictionary containing the classification result with at least
                  an 'invoice_type' key. The exact structure depends on the
                  InvoiceDetector implementation.
        """
        my_logger.info("📋 Classifying invoice...")
        clf = InvoiceDetector()
        result = await clf.adetect(input_text=processed_doc)

        # Check if classification was successful
        if "error" in result:
            raise ValueError(f"Classification error: {result['error']}")

        if "invoice_type" not in result:
            raise ValueError("Missing 'invoice_type' in classification result")

        return result

    async def classify_invoice(self, state: DocState) -> Command[Literal["extract"]]:
        """
        Classifies the type of invoice using the InvoiceDetector.

        This method uses the processed document text from the state to classify the invoice type.
        If the classification fails after retries, it defaults to "unknown" type and continues processing.

        Args:
            state (DocState): The current state containing the processed document text.

        Returns:
            Command: The next command to execute in the workflow.
        """
        try:
            result = await self._classify_document(state["processed_doc"])
            my_logger.info(f"✅ Classification complete: {result['invoice_type']}")

            return Command(
                update={
                    "invoice_type": result["invoice_type"],
                    "inferred_types": [result["invoice_type"]],
                },
                goto="extract",
            )

        except Exception as e:
            my_logger.error(f"❌ Classification failed after all retries: {str(e)}")
            # Use default type but still proceed to extraction
            return Command(
                update={
                    "invoice_type": "unknown",
                    "inferred_types": ["unknown"],
                },
                goto="extract",  # Still try to extract with unknown type
            )

    # def get_conversion_info(state: DocState) -> Command:
    #     rate_info = create_conversion_info(state)
    #     return Command(update={"rate_info": rate_info}, goto="summarize")

    def update_xlsx_file(self, state: DocState) -> Command:
        """
        Write the accumulated extraction result into the travel-expense workbook.

        Args:
            state (DocState): The current processing state.

        Returns:
            Command: A command to proceed to the next step in the workflow.
        """
        my_logger.info("🤖 Editing XLSX file next...")
        update_travel_expense_xlsx(result=state, **self.input_args)

        my_logger.info("🎉 XLSX file updated successfully.")
        return Command(goto=END)

    async def summarize(self, state: DocState) -> Command[Literal["update_xlsx"]]:
        """
        Generates a summary of extracted entities from the given document state.

        This method logs the summarization process, ensures that entities are present in the state,
        creates exchange rate information, and uses a prompt template with a language model to
        generate a summary. The summary is then returned as part of a Command object to update the
        state and proceed to the end of the workflow.

        Args:
            state (DocState): The current document state containing extracted entities and other relevant data.

        Returns:
            Command: A command object containing the generated summary and the next workflow step.
        """

        my_logger.info("🤖 Summarizing entities...")
        assert "entities" in state, "No entities found in the result."

        self.rate_info = create_conversion_info(state)

        summary_templ = PromptTemplate(
            template=summary_prompt,
            input_variables=["context", "info_exchange_rate"],
        )

        chain = summary_templ | self.llm

        response = await chain.ainvoke(
            {"context": state["entities"], "info_exchange_rate": self.rate_info}
        )
        my_logger.info("✅ Summary generated successfully.")
        return Command(
            update={
                "summary": response.content,
                "rate_info": self.rate_info,
            },
            goto="update_xlsx",
            # goto=END,
        )

    def _initialize_graph(self) -> CompiledStateGraph:
        """
        Build and compile the state graph for the document processing workflow.

        Returns:
            The compiled LangGraph state graph.
        """
        graph = StateGraph(DocState)
        graph.add_node("load", self.load_next_file)
        graph.add_node("process", self.process_document)
        graph.add_node("classify", self.classify_invoice)
        graph.add_node("extract", self.extract_and_convert)
        graph.add_node("summarize", self.summarize)
        graph.add_node("update_xlsx", self.update_xlsx_file)
        graph.add_edge(START, "load")

        # # Use add_conditional_edges for conditional routing after "load"
        # def load_router(state):
        #     if state.get("current_file_index", 0) >= len(state.get("file_names", [])):
        #         return "summarize"
        #     else:
        #         return "process"

        # graph.add_conditional_edges("load", load_router)

        # Compile the graph
        processor_graph = graph.compile()
        return processor_graph

    async def ainvoke(self) -> GraphResult:
        """
        Asynchronously invokes the processor graph with the initial state and processes the result.

        This method calls the `ainvoke` method of the `processor_graph` object, passing the
        `initial_state` as input. It then processes the result by adding inferred types to
        the corresponding entities in the result for later use.

        Returns:
            The final workflow state including extracted entities and summary data.
        """
        result = await self.processor_graph.ainvoke(
            self.initial_state, config={"recursion_limit": 50}
        )

        # Add the inferred types to the entities for later use
        for i, typ in enumerate(result["inferred_types"]):
            result["entities"][i]["invoice_type"] = typ
        return result

    def invoke(self) -> GraphResult:
        """
        Executes the processor graph with the initial state and processes the result.

        This method invokes the `processor_graph` using the `initial_state` and processes
        the output by adding inferred types to the corresponding entities in the result.

        Returns:
            The final workflow state including extracted entities and summary data.
        """
        result = self.processor_graph.invoke(
            self.initial_state, config={"recursion_limit": 50}
        )

        # Add the inferred types to the entities for later use
        for i, typ in enumerate(result["inferred_types"]):
            result["entities"][i]["invoice_type"] = typ
        return result
