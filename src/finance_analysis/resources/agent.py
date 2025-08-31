import os
from typing import TypedDict, Annotated, List, Dict
from operator import add
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command
from finance_analysis.resources.extractor import EntityExtractor
from finance_analysis.resources.document_processor import DocumentProcessor
from finance_analysis.resources.invoice_classifier import InvoiceDetector
from finance_analysis.services.logger import LoggerFactory
from langchain.prompts import PromptTemplate
from finance_analysis.resources.get_models import InitModels
from finance_analysis.utils.prompts import summary_prompt
from finance_analysis.utils.utils import (
    convert_currency,
    create_conversion_info,
    update_travel_expense_xlsx,
)
from finance_analysis.utils.data_models import XlsOutputArgs
from finance_analysis.utils.data_models import CurrencyCodeLiteral

my_logger = LoggerFactory(handler_type="Stream").create_module_logger()


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


class ProcessorGraph:
    """
    ProcessorGraph class orchestrates the document processing workflow,
    including loading files, processing documents, classifying invoices,
    and extracting entities.
    """

    def __init__(
        self,
        list_of_files: list[str],
        xls_output_file_args: XlsOutputArgs | None = None,
    ):
        """
        Initialize the Supervisor instance.
        """
        self.initial_state = {
            "file_names": list_of_files,
            "current_index": 0,
            "entities": [],
            "inferred_types": [],
        }
        models = InitModels()
        self.llm = models.llm
        if xls_output_file_args is None:
            xls_output_file_args = XlsOutputArgs()
        self.input_args: Dict[str, str] = xls_output_file_args.to_xlsx_format()
        self.processor_graph = self._initialize_graph()
        my_logger.info(
            f"🤖 Supervisor initialized with {len(list_of_files)} files to process."
        )

    @staticmethod
    def load_next_file(state: DocState) -> Command:
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
            return Command(goto="summarize")

        base_name = os.path.basename(file_list[index])

        my_logger.info(f"📁 Loading file: {base_name}")
        return Command(
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

    def process_document(self, state: DocState) -> Command:
        """
        Processes the current document by reading and converting it to markdown.

        Args:
            state (DocState): The current processing state.

        Returns:
            Command: The next command to execute in the workflow.
        """
        base_name = os.path.basename(state["file_name"])
        my_logger.info(f"📋 Processing file: {base_name}")

        dproc = DocumentProcessor(file_path=state["file_name"])
        document = dproc.process()
        processed = document.export_to_markdown()
        return Command(update={"processed_doc": processed}, goto="classify")

    @staticmethod
    async def extract_and_convert(state: DocState) -> Command:
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
            # 1) pull raw entities from doc
            extracted = await EntityExtractor(state["invoice_type"]).aextract_entities(
                state["processed_doc"]
            )

            # 2) convert immediately
            amount = float(extracted["total_amount"])
            from_cur = extracted["currency"]

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
    async def classify_invoice(state: DocState) -> Command:
        """
        Classifies the invoice type of the processed document.

        Args:
            state (DocState): The current processing state.

        Returns:
            Command: The next command to execute in the workflow.
        """
        try:
            my_logger.info("📋 Classifying invoice...")
            clf = InvoiceDetector()
            result = await clf.adetect(input_text=state["processed_doc"])
            my_logger.info(f"✅ Classification complete: {result['invoice_type']}")

            return Command(
                update={
                    "invoice_type": result["invoice_type"],
                    "inferred_types": [result["invoice_type"]],
                },
                goto="extract",
            )
        except Exception as e:
            my_logger.error(f"❌ Classification failed: {str(e)}")
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
        Placeholder for a method to edit an XLSX file based on the current state.
        This method is not implemented yet.

        Args:
            state (DocState): The current processing state.

        Returns:
            Command: A command to proceed to the next step in the workflow.
        """
        my_logger.info("🤖 Editing XLSX file next...")
        update_travel_expense_xlsx(result=state, **self.input_args)

        my_logger.info("🎉 XLSX file updated successfully.")
        return Command(goto=END)

    async def summarize(self, state: DocState) -> Command:
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

    def _initialize_graph(self) -> StateGraph:
        """
        Builds the state graph for the document processing workflow.

        Returns:
            StateGraph: The compiled state graph.
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

    async def ainvoke(self) -> dict:
        """
        Asynchronously invokes the processor graph with the initial state and processes the result.

        This method calls the `ainvoke` method of the `processor_graph` object, passing the
        `initial_state` as input. It then processes the result by adding inferred types to
        the corresponding entities in the result for later use.

        Returns:
            dict: A dictionary containing the processed result, including entities with
            their associated inferred types.
        """
        result = await self.processor_graph.ainvoke(
            self.initial_state, config={"recursion_limit": 50}
        )

        # Add the inferred types to the entities for later use
        for i, typ in enumerate(result["inferred_types"]):
            result["entities"][i]["invoice_type"] = typ
        return result

    def invoke(self) -> dict:
        """
        Executes the processor graph with the initial state and processes the result.

        This method invokes the `processor_graph` using the `initial_state` and processes
        the output by adding inferred types to the corresponding entities in the result.

        Returns:
            dict: A dictionary containing the processed result, including entities with
                  their associated inferred types.
        """
        result = self.processor_graph.invoke(
            self.initial_state, config={"recursion_limit": 50}
        )

        # Add the inferred types to the entities for later use
        for i, typ in enumerate(result["inferred_types"]):
            result["entities"][i]["invoice_type"] = typ
        return result
