# from typing import Union, List, Literal, Optional
from langchain_ollama.chat_models import ChatOllama
from langchain_ollama import OllamaEmbeddings
from langchain_google_vertexai import VertexAIEmbeddings, ChatVertexAI
from finance_analysis.config.config import model_list
from finance_analysis.config import global_config as glob
from finance_analysis.services.logger import LoggerFactory

my_logger = LoggerFactory(handler_type="Stream", verbose=True).create_module_logger()


class InitModels:

    def __init__(
        self,
        model_provider: str = glob.MODEL_PROVIDER,
    ) -> None:

        # my_logger.info(f"Fetching {model_provider} models")

        selected_chat_model = model_list["chat_model"][glob.MODEL_PROVIDER]
        selected_embed_model = model_list["embedding_model"][glob.MODEL_PROVIDER]

        match model_provider:
            case "google":
                self.llm = ChatVertexAI(
                    project=glob.GCP_PROJECT,
                    model_name=selected_chat_model,
                    temperature=0.1,
                    max_retries=2,
                )
                self.embedding_model = VertexAIEmbeddings(
                    model_name=selected_embed_model, project=glob.GCP_PROJECT
                )
            case "ollama":
                self.llm = ChatOllama(
                    model=selected_chat_model,
                    temperature=0.1,
                )
                self.embedding_model = OllamaEmbeddings(model=selected_embed_model)
            case _:
                raise ValueError(f"Model provider {glob.MODEL_PROVIDER} not supported.")
        # my_logger.info(f"Models loaded successfully")
