from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from finance_analysis.resources.get_models import InitModels
from finance_analysis.config.config import invoice_list, currency_list
from finance_analysis.utils import prompts, data_models


class EntityExtractor:
    def __init__(self, invoice_type: str) -> None:

        prompt_templ = getattr(
            prompts, invoice_list["types"].get(invoice_type, "taxi")["prompt_template"]
        )

        OutBaseModel = getattr(
            data_models,
            invoice_list["types"].get(invoice_type, "taxi")["output_format"],
        )

        self.parser = JsonOutputParser(pydantic_object=OutBaseModel)

        self.prompt_template = PromptTemplate(
            template=prompt_templ,
            input_variables=["context"],
            partial_variables={
                "format_instructions": self.parser.get_format_instructions(),
                "currency_list": list(currency_list["abbreviations"].keys()),
            },
        )

        # Initialize models
        models = InitModels()
        self.llm, self.embedding_model = models.llm, models.embedding_model

    def extract_entities(self, markdown: str) -> dict:
        """
        Extract entities from a given markdown string using a processing chain.

        This method utilizes a chain of components including a prompt template,
        a language model (LLM), and a parser to process the input markdown and
        extract relevant entities.

        Args:
            markdown (str): The input markdown string containing the context
                            from which entities need to be extracted.

        Returns:
            dict: A dictionary containing the extracted entities.
        """
        chain = self.prompt_template | self.llm | self.parser

        response = chain.invoke({"context": markdown})
        return response

    async def aextract_entities(self, markdown: str) -> dict:
        """
        Asynchronously extracts entities from the given markdown text.

        This method utilizes a processing chain composed of a prompt template,
        a language model (LLM), and a parser to extract structured information
        from the provided markdown content.

        Args:
            markdown (str): The markdown text from which entities are to be extracted.

        Returns:
            dict: A dictionary containing the extracted entities.
        """
        chain = self.prompt_template | self.llm | self.parser

        response = await chain.ainvoke({"context": markdown})
        return response
