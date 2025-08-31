import os
import warnings
from IPython.display import Markdown, display
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions, TesseractOcrOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling_core.types.doc import DoclingDocument
from finance_analysis.services.logger import LoggerFactory

my_logger = LoggerFactory(handler_type="Stream", verbose=True).create_module_logger()


class DocumentProcessor:
    """
    A class to handle the conversion of documents using a DocumentConverter.

    Attributes:
        file_path (str): The path to the file to be converted.
        converter (DocumentConverter): An instance of the DocumentConverter class.
        result: The result of the document conversion, initialized as None.

    Methods:
        convert():
            Converts the document at the specified file path and stores the result.

        display_markdown():
            Displays the converted document in Markdown format if a conversion result is available.
            Prints a message if no conversion result is available.
    """

    def __init__(self, file_path):
        self.file_path = file_path

        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = True
        # pipeline_options.ocr_options = TesseractOcrOptions(
        #     lang=["eng"]
        # )  # or use other OCR option classes

        docling_options = {
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
        }

        self.converter = DocumentConverter(format_options=docling_options)
        self.result = None

    def process(self) -> DoclingDocument:
        """
        Converts the document at the specified file path using the assigned converter.

        This method attempts to convert the document and logs the success or failure
        of the operation. If the conversion is successful, the resulting document is
        returned. In case of an error, the exception is logged and re-raised.

        Returns:
            DoclingDocument: The converted document.
        """
        try:
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore")
                self.result = self.converter.convert(
                    self.file_path, raises_on_error=False
                )
            my_logger.info(
                f"✅ Document converted successfully: {os.path.basename(self.file_path)}"
            )
            return self.result.document
        except Exception as e:
            my_logger.error(f"❌ Error converting document: {e}")
            raise e

    def display_markdown(self, **kwargs) -> None:
        if self.result is not None:
            markdown = self.result.document.export_to_markdown()
            display(Markdown(markdown), **kwargs)
        else:
            print("⚠️ No conversion result available. Please run convert() first.")
