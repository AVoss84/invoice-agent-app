from tqdm.auto import tqdm
from typing import Optional, List, Tuple, Dict, Any, Union
from langchain.vectorstores import FAISS
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_google_vertexai import VertexAIEmbeddings

# from langchain_experimental.text_splitter import SemanticChunker
from langchain_ollama import OllamaEmbeddings
from langchain_core.language_models.llms import LLM
from langchain.docstore.document import Document
from langchain.chains.retrieval import create_retrieval_chain
from langchain.prompts import PromptTemplate, ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from langchain_core.vectorstores import VectorStore
from langchain.chains.combine_documents import create_stuff_documents_chain
from finance_analysis.config import global_config as glob
from finance_analysis.config.config import model_list
from finance_analysis.utils.prompts import rag_prompt


def build_vectorstore(
    langchain_docs: List[Document],
    **chunker_kwargs: Any,
) -> VectorStore:
    embedding_model: Union[VertexAIEmbeddings, OllamaEmbeddings]
    """
    Loads embeddings for a list of documents and returns a vector store.

    Args:
        langchain_docs (List[Document]): A list of documents to be embedded
        chunker_kwargs (Any): Additional keyword arguments for the text splitter

    Returns:
        VectorStore: A vector store containing the embedded documents.
    """
    # Embedding models available
    google_embedding = model_list["embedding_model"].get(glob.MODEL_PROVIDER, "google")
    ollama_embedding = model_list["embedding_model"].get("ollama")

    google_embedding_model = google_embedding[list(google_embedding.keys())[0]]
    ollama_embedding_model = ollama_embedding[list(ollama_embedding.keys())[0]]

    if glob.MODEL_PROVIDER == "google":
        embedding_model = VertexAIEmbeddings(
            project="onc-ai-sandbox", model_name=google_embedding_model
        )
    elif glob.MODEL_PROVIDER == "ollama":
        embedding_model = OllamaEmbeddings(model=ollama_embedding_model)
    else:
        raise ValueError("Invalid model provider")

    print("Chunking documents.")
    # text_splitter = SemanticChunker(embedding_model, **chunker_kwargs)
    text_splitter = RecursiveCharacterTextSplitter(**chunker_kwargs)
    docs_processed = text_splitter.split_documents(langchain_docs)

    print("Building vector store.")
    vectorstore = FAISS.from_documents(
        documents=docs_processed,
        embedding=embedding_model,
    )
    print("Vector store built.")
    return vectorstore


async def answer_with_rag(
    question: str,
    llm: LLM,
    vectorstore: VectorStore,
    num_docs_final: int = 7,
) -> Tuple[str, List[Document]]:
    """
    Generate an answer to a question using Retrieval-Augmented Generation (RAG).
    This function uses a combination of document retrieval and language model generation
    to produce a concise answer to the given question. It optionally reranks the retrieved
    documents to improve the relevance of the final answer.
    Args:
        question (str): The question to be answered.
        llm (LLM): The language model to generate the final answer.
        vectorstore (VectorStore): The vector store used for document retrieval.
        num_docs_final (int): The number of final documents to consider after reranking.
    Returns:
        Tuple[str, List[Document]]: A tuple containing the generated answer and the list of relevant documents.
    """

    rag_retrieval_prompt = PromptTemplate(
        input_variables=["context"],
        template="You are an AI document retrieval assistant. \
            Using the following context generate a concise answer: {context}\n\n \
            Output also the source of the information. \
            Answer:",
    )

    rag_generator_prompt = PromptTemplate(
        input_variables=["context", "question"],
        template=rag_prompt,
    )
    # 1.) Build the retriever part
    retriever = vectorstore.as_retriever()
    combine_docs_chain = create_stuff_documents_chain(llm, rag_retrieval_prompt)
    retrieval_chain = create_retrieval_chain(retriever, combine_docs_chain)
    retrieval_result = retrieval_chain.invoke({"input": question})

    answer = retrieval_result["answer"]
    relevant_docs = retrieval_result["context"]

    # Ensure relevant_docs is iterable
    if relevant_docs is None:
        relevant_docs = []

    relevant_docs = [doc.page_content for doc in relevant_docs]  # keep only the text

    # Build the final prompt
    context = "\nExtracted documents:\n"
    context += "".join(
        [f" Document No. {str(i)}: " + doc for i, doc in enumerate(relevant_docs)]
    )
    # 2.) Build the generator part:
    final_prompt = rag_generator_prompt.format(context=context, question=question)
    answer = await llm.ainvoke(final_prompt)

    return answer, relevant_docs


def chat_llm(prompt: PromptTemplate, llm: LLM, **inputs: str) -> str:
    """
    Call a language model with a given prompt template and inputs.

    This function processes a prompt through a language model and returns the response as a string.

    Args:
        prompt (PromptTemplate): The template to format with input variables
        llm (LLM): The language model to process the prompt
        **inputs: Variable keyword arguments to populate the prompt template

    Returns:
        str: The processed response from the language model

    Example:
        >>> prompt = PromptTemplate("Answer this question: {question}")
        >>> llm = ChatOpenAI()
        >>> response = chat_llm(prompt, llm, question="What is 2+2?")
    """

    question_router = prompt | llm | StrOutputParser()
    return question_router.invoke(inputs)


async def chat_llm_async(prompt: PromptTemplate, llm: LLM, **inputs: str) -> str:
    """
    Call a language model asynchronously with a given prompt template and inputs.

    This function processes a prompt through a language model and returns the response as a string.

    Args:
        prompt (PromptTemplate): The template to format with input variables
        llm (LLM): The language model to process the prompt
        **inputs: Variable keyword arguments to populate the prompt template

    Returns:
        str: The processed response from the language model
    """
    question_router = prompt | llm | StrOutputParser()
    res = await question_router.ainvoke(inputs)
    return res
