import os
import asyncio
from logging import Logger
import tempfile, warnings
from PIL import Image
import base64
from io import BytesIO
import streamlit as st
from finance_analysis.config import global_config as glob
from finance_analysis.services.logger import LoggerFactory
from finance_analysis.resources.document_processor import DocumentProcessor
from finance_analysis.resources.agent import ProcessorGraph
from finance_analysis.utils.utils import merge_pdfs


def get_logger() -> Logger:
    if "logger" not in st.session_state:
        st.session_state.logger = LoggerFactory(
            handler_type="Stream", verbose=True
        ).create_module_logger()
    return st.session_state.logger


def display_logo() -> None:
    try:
        logo = Image.open(f"{glob.DATA_PKG_DIR}/NemetschekGroup_White_72dpi_oRand.png")
        st.image(logo, width=350)
    except FileNotFoundError:
        st.error("Logo file not found!")


def display_pdf(file: BytesIO) -> None:
    """
    Displays a PDF file in a Streamlit app using an iframe.

    Args:
        file (BytesIO): A BytesIO object containing the PDF file data.
        width (str, optional): The width of the iframe displaying the PDF. Defaults to "100%".
        height (str, optional): The height of the iframe displaying the PDF. Defaults to "900".

    Returns:
        None: This function does not return a value. It renders the PDF in the Streamlit app.
    """
    bytes_data = file.getvalue()
    base64_pdf = base64.b64encode(bytes_data).decode("utf-8")
    pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="700" type="application/pdf"></iframe>'
    st.markdown(pdf_display, unsafe_allow_html=True)


logger = get_logger()


def main() -> None:

    st.set_page_config(
        page_title="Reimbursement Copilot",
        page_icon="📚",
        layout="wide",
    )

    # Initialize session state variables if they don't exist
    if "file_path" not in st.session_state:
        st.session_state.file_path = None
    if "markdown" not in st.session_state:
        st.session_state.markdown = None
    if "document" not in st.session_state:
        st.session_state.document = None

    # Header with logo
    display_logo()
    st.markdown("<br>", unsafe_allow_html=True)

    # Create tabs
    upload_tab, multi_tab = st.tabs(["📁 Extract Text", "📑 Multi-file Processing"])

    # Upload Tab with GCP functionality
    # -----------------------------------
    with upload_tab:

        pdf_file = st.file_uploader(
            "Choose a PDF file",
            type=["pdf"],
            help="Upload a PDF document",
        )

        if pdf_file:
            # Get the name of the uploaded file
            uploaded_file_name = pdf_file.name
            st.session_state.file_path = uploaded_file_name

            # Save the uploaded file to a temporary location
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
                temp_file.write(pdf_file.getbuffer())
                temp_path_name = temp_file.name

            # Process the document
            dproc = DocumentProcessor(file_path=temp_path_name)
            document = dproc.process()

            # Get the Markdown output
            markdown = document.export_to_markdown()

            # save as state
            st.session_state.markdown = markdown
            st.session_state.document = document

            # Display the PDF and Markdown side by side
            col1, col2 = st.columns(spec=2, gap="large")

            st.markdown("---")

            with col1:
                st.subheader("Original File")
                st.markdown("<br>", unsafe_allow_html=True)
                display_pdf(pdf_file)

            with col2:
                st.subheader("Extracted Content")
                st.markdown("<br>", unsafe_allow_html=True)

                # Wrap the Markdown in a scrollable div
                scrollable_markdown = f"""
                <div style="
                    height:700px;
                    overflow-y:scroll;
                    border:1px solid #ccc;
                    padding:10px;
                    background-color:#002b36;
                    color:#fafafa;
                    line-height:1.0;
                    font-size: 1rem;
                ">
                    {st.session_state.markdown}
                </div>
                """
                st.markdown(scrollable_markdown, unsafe_allow_html=True)

    # Multi-file Processing Tab
    with multi_tab:
        # st.subheader("Upload Multiple PDF Files for Batch Processing")
        uploaded_files = st.file_uploader(
            "Choose invoices for processing:",
            type=["pdf"],
            accept_multiple_files=True,
            help="Upload one or more PDF invoices",
        )

        st.markdown("<br>", unsafe_allow_html=True)

        st.session_state.xls_file_name = st.text_input(
            label="Enter name for output XLS file:",
            value="my_travel_expenses.xlsx",
            help="Provide a name for the output Excel file (default: my_travel_expense.xlsx)",
        )

        if st.button("Process Uploaded Files"):
            if uploaded_files:
                # Save uploaded files to temp and collect their paths and names
                temp_dir = tempfile.mkdtemp()
                temp_paths = []
                temp_names = []
                for file in uploaded_files:
                    temp_path = os.path.join(temp_dir, file.name)
                    with open(temp_path, "wb") as temp_file:
                        temp_file.write(file.getbuffer())
                    temp_paths.append(temp_path)
                    temp_names.append(file.name)

                # Merge PDFs
                merged_pdf_path = os.path.join(temp_dir, "merged.pdf")
                merge_pdfs(
                    pdf_dir=temp_dir, pdf_names=temp_names, output_file="merged.pdf"
                )

                # Pass temp_paths as list_of_files to your processor
                supervisor = ProcessorGraph(
                    list_of_files=temp_paths,
                    target_xls_file=st.session_state.xls_file_name,
                )

                with st.spinner("Processing your invoices... (please wait ⏱️)"):
                    result = asyncio.run(supervisor.ainvoke())

                st.markdown("---")

                # Display merged PDF and markdown result side by side
                col1, col2 = st.columns(2, gap="large")
                with col1:
                    st.subheader("Original")
                    with open(merged_pdf_path, "rb") as f:
                        merged_pdf_bytes = BytesIO(f.read())
                    display_pdf(merged_pdf_bytes)
                with col2:
                    st.subheader("Summary")
                    st.markdown("<br>", unsafe_allow_html=True)
                    st.markdown(result["summary"], unsafe_allow_html=True)
                st.toast(
                    f"File: {st.session_state.xls_file_name} created!",
                    icon="🎉",
                )
                st.snow()
            else:
                st.warning("Please upload at least one PDF file!")


if __name__ == "__main__":
    main()
