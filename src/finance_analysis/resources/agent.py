import os
import warnings
from typing import TypedDict, Annotated
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
from finance_analysis.utils.data_models import CurrencyCodeLiteral

my_logger = LoggerFactory(handler_type="Stream").create_module_logger()

warnings.filterwarnings("ignore")


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
        source_path: str = "/Users/avosseler/Business Trips/2025/Barcelona",
        target_xls_file: str = "Travel Expense Tmp Edt.xlsx",
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
        self.source_path = source_path
        self.target_xls_file = target_xls_file
        self.processor_graph = self._initialize_graph()
        my_logger.info(
            f"Supervisor initialized with {len(list_of_files)} files to process."
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
        index = state.get("current_file_index", 0)
        file_list = state.get("file_names", [])

        # Finally: Goto Summarization if no more files
        if index >= len(file_list):
            return Command(goto="summarize")

        print(f"\nLoading file: {file_list[index]}")
        return Command(
            update={"file_name": file_list[index], "current_file_index": index + 1},
            goto="process",  # next step (-> edge)
        )

    def process_document(self, state: DocState) -> Command:
        """
        Processes the current document by reading and converting it to markdown.

        Args:
            state (DocState): The current processing state.

        Returns:
            Command: The next command to execute in the workflow.
        """
        my_logger.info(f"Processing file: {state['file_name']}")
        file_path = os.path.join(self.source_path, state["file_name"])

        dproc = DocumentProcessor(file_path=file_path)
        document = dproc.process()
        processed = document.export_to_markdown()
        return Command(update={"processed_doc": processed}, goto="classify")

    @staticmethod
    async def extract_and_convert(state: DocState) -> Command:

        # 1) pull raw entities
        extracted = await EntityExtractor(state["invoice_type"]).aextract_entities(
            state["processed_doc"]
        )

        # 2) convert immediately
        amount = float(extracted["total_amount"])
        from_cur = extracted["currency"]

        print(f"Converting {amount} {from_cur} to EUR...")
        conv = convert_currency(amount, from_cur)
        print(f"Converted amount: {conv['EUR Amount']} EUR")

        extracted["total_amount"] = conv["EUR Amount"]
        extracted["currency"] = "EUR"
        extracted["invoice_type"] = state.get("invoice_type", "unknown")

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
        my_logger.info("Classifying invoice...")
        clf = InvoiceDetector()
        result = await clf.adetect(input_text=state["processed_doc"])

        return Command(
            update={
                "invoice_type": result["invoice_type"],
                "inferred_types": [result["invoice_type"]],
            },
            goto="extract",
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
        my_logger.info("Editing XLSX file...")
        update_travel_expense_xlsx(result=state, output_file=self.target_xls_file)

        my_logger.info("XLSX file updated successfully.")
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

        my_logger.info("Summarizing entities...")
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
        my_logger.info("Summary generated successfully.")
        return Command(
            update={
                "summary": response.content,
                "rate_info": self.rate_info,
            },
            goto="update_xlsx",
            # goto=END,
        )

    def _initialize_graph(self):
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

        result = await self.processor_graph.ainvoke(self.initial_state)

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

        result = self.processor_graph.invoke(self.initial_state)

        # Add the inferred types to the entities for later use
        for i, typ in enumerate(result["inferred_types"]):
            result["entities"][i]["invoice_type"] = typ
        return result
