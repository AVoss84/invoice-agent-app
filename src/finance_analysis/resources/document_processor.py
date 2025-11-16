import os
import warnings
from typing import Any, Optional
from IPython.display import Markdown, display
from google.api_core.client_options import ClientOptions
from google.cloud import documentai_v1 as documentai

# from docling.datamodel.base_models import InputFormat
# from docling.datamodel.pipeline_options import PdfPipelineOptions, TesseractOcrOptions
# from docling.document_converter import DocumentConverter, PdfFormatOption
# from docling_core.types.doc import DoclingDocument
from finance_analysis.services.logger import LoggerFactory

my_logger = LoggerFactory().create_module_logger()


# class DocumentProcessor:
#     """
#     A class to handle the conversion of documents using a DocumentConverter.

#     Attributes:
#         file_path (str): The path to the file to be converted.
#         converter (DocumentConverter): An instance of the DocumentConverter class.
#         result: The result of the document conversion, initialized as None.

#     Methods:
#         convert():
#             Converts the document at the specified file path and stores the result.

#         display_markdown():
#             Displays the converted document in Markdown format if a conversion result is available.
#             Prints a message if no conversion result is available.
#     """

#     def __init__(self, file_path: str) -> None:
#         self.file_path: str = file_path

#         pipeline_options = PdfPipelineOptions()
#         pipeline_options.do_ocr = True
#         # pipeline_options.ocr_options = TesseractOcrOptions(
#         #     lang=["eng"]
#         # )  # or use other OCR option classes

#         docling_options = {
#             InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
#         }

#         self.converter = DocumentConverter(format_options=docling_options)
#         self.result: Optional[Any] = None

#     def process(self) -> DoclingDocument:
#         """
#         Converts the document at the specified file path using the assigned converter.

#         This method attempts to convert the document and logs the success or failure
#         of the operation. If the conversion is successful, the resulting document is
#         returned. In case of an error, the exception is logged and re-raised.

#         Returns:
#             DoclingDocument: The converted document.
#         """
#         try:
#             with warnings.catch_warnings():
#                 warnings.filterwarnings("ignore")
#                 self.result = self.converter.convert(
#                     self.file_path, raises_on_error=False
#                 )
#             my_logger.info(
#                 f"✅ Document converted successfully: {os.path.basename(self.file_path)}"
#             )
#             return self.result.document
#         except Exception as e:
#             my_logger.error(f"❌ Error converting document: {e}")
#             raise e

#     def display_markdown(self, **kwargs: Any) -> None:
#         if self.result is not None:
#             markdown = self.result.document.export_to_markdown()
#             display(Markdown(markdown), **kwargs)
#         else:
#             print("⚠️ No conversion result available. Please run convert() first.")


class DocumentProcessor_GCP:
    """
    A class to handle document processing using Google Cloud Document AI.

    Attributes:
        file_path (str): The path to the file to be processed.
        project_id (str): The GCP project ID.
        location (str): The GCP location (e.g., 'eu', 'us').
        processor_id (str): The Document AI processor ID.
        result: The result of the document processing, initialized as None.

    Methods:
        process():
            Processes the document using Document AI and stores the result.

        display_markdown():
            Displays the processed document in Markdown format if a result is available.
    """

    def __init__(
        self,
        file_path: str,
        project_id: str,
        location: str,
        processor_id: str,
        mime_type: str = "application/pdf",
    ) -> None:
        self.file_path: str = file_path
        self.project_id: str = project_id
        self.location: str = location
        self.processor_id: str = processor_id
        self.mime_type: str = mime_type

        client_options = ClientOptions(
            api_endpoint=f"{location}-documentai.googleapis.com"
        )
        self.client: documentai.DocumentProcessorServiceClient = (
            documentai.DocumentProcessorServiceClient(client_options=client_options)
        )
        self.result: Optional[dict[str, Any]] = None

    def process(self) -> dict[str, Any]:
        """
        Processes the document at the specified file path using Document AI.

        Returns:
            dict: The processed document as a dictionary.
        """
        try:
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore")

                name = self.client.processor_path(
                    self.project_id, self.location, self.processor_id
                )

                with open(self.file_path, "rb") as f:
                    file_content = f.read()

                raw_document = documentai.RawDocument(
                    content=file_content, mime_type=self.mime_type
                )
                request = documentai.ProcessRequest(
                    name=name, raw_document=raw_document
                )
                response = self.client.process_document(request=request)

                self.result = documentai.Document.to_dict(response.document)

            my_logger.info(
                f"✅ Document processed successfully: {os.path.basename(self.file_path)}"
            )
            assert self.result is not None
            return self.result

        except Exception as e:
            my_logger.error(f"❌ Error processing document: {e}")
            raise e

    def display_markdown(self, **kwargs: Any) -> None:
        if self.result is not None:
            markdown = self.to_markdown()
            display(Markdown(markdown), **kwargs)
        else:
            print("⚠️ No processing result available. Please run process() first.")

    def to_markdown(self) -> str:
        """
        Convert a document dictionary to Markdown format.

        This method processes a document dictionary containing document layout information
        and converts it into a Markdown-formatted string. It handles text blocks (including
        headings) and table blocks, formatting them appropriately for Markdown output.

        Returns:
            str: A Markdown-formatted string representation of the document. Text blocks
                are converted to paragraphs or headings based on their type, and table
                blocks are formatted as Markdown tables.
        """
        lines: list[str] = []
        table_rows: list[list[str]] = []

        for block in self.result.get("document_layout", {}).get("blocks", []):
            if "text_block" in block and (
                text := block["text_block"].get("text", "").strip()
            ):
                if table_rows:
                    lines.extend(self._format_table(table_rows))
                    table_rows = []

                block_type = block["text_block"].get("type_", "paragraph")
                prefix = (
                    "\n# "
                    if block_type == "heading-1"
                    else "\n## " if block_type == "heading-2" else ""
                )
                lines.append(f"{prefix}{text}\n")

            elif "table_block" in block:
                for row in block["table_block"].get("body_rows", []):
                    row_data = [
                        " ".join(
                            cb["text_block"].get("text", "").strip()
                            for cb in cell.get("blocks", [])
                            if "text_block" in cb
                        )
                        or "-"
                        for cell in row.get("cells", [])
                    ]
                    if any(r != "-" for r in row_data):
                        table_rows.append(row_data)

        if table_rows:
            lines.extend(self._format_table(table_rows))

        return "\n".join(lines)

    def _format_table(self, rows: list[list[str]]) -> list[str]:
        """
        Format a table of rows into a markdown table string.

        This method takes a list of rows (each row being a list of strings) and converts
        it into a markdown-formatted table. It handles:
        - Padding rows with "-" to ensure all rows have the same number of columns
        - Auto-detecting if the first row is a header (if at least half of its cells are non-empty)
        - Generating default column names (Col1, Col2, etc.) if no header is detected
        - Creating proper markdown table syntax with headers and separators

        Args:
            rows (list[list[str]]): A list of rows, where each row is a list of string values
                                   representing table cells.

        Returns:
            list[str]: A list of strings representing the markdown-formatted table lines,
                      including header row, separator row, data rows, and a trailing empty line.

        Example:
            >>> rows = [["Name", "Age"], ["Alice", "30"], ["Bob"]]
            >>> result = self._format_table(rows)
            >>> print("\\n".join(result))
            | Name | Age |
            | --- | --- |
            | Alice | 30 |
            | Bob | - |
        """
        max_cols = max(len(r) for r in rows)
        rows = [r + ["-"] * (max_cols - len(r)) for r in rows]

        has_header = (
            len(rows) > 1 and sum(bool(c != "-") for c in rows[0]) >= max_cols // 2
        )
        header = rows[0] if has_header else [f"Col{i+1}" for i in range(max_cols)]
        data = rows[1:] if has_header else rows

        return [
            "\n| " + " | ".join(header) + " |",
            "| " + " | ".join(["---"] * max_cols) + " |",
            *["| " + " | ".join(r) + " |" for r in data],
            "",
        ]
