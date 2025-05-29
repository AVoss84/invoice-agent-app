from langchain_google_vertexai import ChatVertexAI
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_google_vertexai import ChatVertexAI
from finance_analysis.config import global_config as glob
from finance_analysis.services.logger import LoggerFactory
from finance_analysis.config.config import invoice_list, model_list
from finance_analysis.utils.data_models import ClassifierOutput

my_logger = LoggerFactory(handler_type="Stream").create_module_logger()


class InvoiceDetector:
    def __init__(self):
        parser = JsonOutputParser(pydantic_object=ClassifierOutput)
        llm = ChatVertexAI(
            project=glob.GCP_PROJECT,
            model_name=model_list["chat_model"].get("google", "gemini-2.0-flash-001"),
            temperature=0,
            max_retries=2,
        )

        self.prompt = PromptTemplate(
            template="""
            Detect the type of the following invoice context and output a JSON object with the key 'invoice-class' 
            and the value out of the following key-value list of invoice types {types}. Assign continous probabilities between 0 and 1 to each type
            and ensure that the probabilities sum to 1. If the detected invoice class/type is not in the provided list, output 'unknown'.
            Input text: {context}\n\n.
            Output:\n{format_instructions}
            """,
            input_variables=["context", "types"],
            partial_variables={"format_instructions": parser.get_format_instructions()},
        )
        self.chain = self.prompt | llm | parser

    def detect(self, input_text: str) -> dict:
        """
        Detects the type of invoice based on the provided input text.

        Args:
            input_text (str): The text content to be analyzed for invoice classification.

        Returns:
            dict: A dictionary containing the classification result. If an error occurs,
                  it returns a dictionary with an "error" key and an appropriate error message.
        """

        try:
            result = self.chain.invoke(
                {"context": input_text, "types": list(invoice_list["types"].keys())}
            )
            return result
        except Exception as e:
            my_logger.error(f"Error in invoice classification: {e}")
            return {"error": "Invoice classification failed."}

    async def adetect(self, input_text: str) -> dict:
        """
        Asynchronously detects and classifies the type of an invoice based on the provided input text.

        Args:
            input_text (str): The text content to be analyzed for invoice classification.

        Returns:
            dict: A dictionary containing the classification result. If successful, it includes the classification details.
                  If an error occurs, it returns a dictionary with an "error" key and a corresponding error message.

        Raises:
            Exception: Logs an error message if the classification process fails.
        """

        try:
            result = await self.chain.ainvoke(
                {"context": input_text, "types": list(invoice_list["types"].keys())}
            )
            return result
        except Exception as e:
            my_logger.error(f"Error in invoice classification: {e}")
            return {"error": "Invoice classification failed."}
