import os
import asyncio
import tempfile
from io import BytesIO
import streamlit as st
from finance_analysis.resources.document_processor import DocumentProcessor
from finance_analysis.resources.agent import ProcessorGraph
from finance_analysis.utils.utils import (
    merge_pdfs,
    display_pdf,
    display_png,
    display_logo,
    get_logger,
)
from finance_analysis.utils.data_models import XlsOutputArgs, TripMetadata
from finance_analysis.services.session_states import SessionStateManager

logger = get_logger()


def main() -> None:

    st.set_page_config(
        page_title="Reimbursement Copilot",
        page_icon="📚",
        layout="wide",
    )

    # Initialize session state using SessionStateManager
    SessionStateManager.initialize()

    # Header with logo
    display_logo()
    st.markdown("<br>", unsafe_allow_html=True)

    # Create tabs
    upload_tab, multi_tab = st.tabs(["📁 Extract Text", "📑 Multi-file Processing"])

    # Upload Tab with GCP functionality
    # -----------------------------------
    with upload_tab:

        # Handle tab switching using SessionStateManager
        SessionStateManager.switch_to_upload_tab()

        uploaded_file = st.file_uploader(
            "Choose a file",
            type=["pdf", "png"],
            help="Upload a PDF/PNG document",
            key="upload_tab_file_uploader",
        )

        if uploaded_file:
            # Get the name of the uploaded file
            uploaded_file_name = uploaded_file.name

            # Only process if it's a new file
            if st.session_state.get("last_uploaded_file") != uploaded_file_name:
                # Determine file type
                file_extension = uploaded_file_name.lower().split(".")[-1]

                # Save the uploaded file to a temporary location
                suffix = f".{file_extension}"
                with tempfile.NamedTemporaryFile(
                    delete=False, suffix=suffix
                ) as temp_file:
                    temp_file.write(uploaded_file.getbuffer())
                    temp_path_name = temp_file.name

                # Process the document
                with st.spinner("Processing document..."):
                    dproc = DocumentProcessor(file_path=temp_path_name)
                    document = dproc.process()
                    markdown = document.export_to_markdown()

                # Store results using SessionStateManager
                SessionStateManager.set_upload_results(
                    uploaded_file_name, markdown, document
                )

        # Display results only if conditions are met
        if SessionStateManager.should_show_upload_results() and uploaded_file:
            # Display the PDF and Markdown side by side
            col1, col2 = st.columns(spec=2, gap="large")

            st.markdown("---")

            with col1:
                st.subheader("Original File")
                st.markdown("<br>", unsafe_allow_html=True)
                # Remove this line: display_pdf(pdf_file)

                # Display based on file type
                file_extension = uploaded_file.name.lower().split(".")[-1]
                if file_extension == "pdf":
                    display_pdf(uploaded_file)
                elif file_extension == "png":
                    display_png(uploaded_file)
                else:
                    st.error(f"Unsupported file type: {file_extension}")

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

        # Handle tab switching using SessionStateManager
        SessionStateManager.switch_to_multi_tab()

        uploaded_files = st.file_uploader(
            "Choose invoices for processing:",
            type=["pdf", "png"],
            accept_multiple_files=True,
            help="Upload one or more invoices",
            key="multi_tab_file_uploader",
        )

        # st.markdown("<br>", unsafe_allow_html=True)

        # Trip Information Section
        st.subheader("Trip Information")

        # Create columns for the input fields
        col1, col2 = st.columns(2)

        with col1:
            last_first_name = st.text_input(
                "Last, First Name",
                value="Vosseler, Alexander",
                help="Enter your name in format: Last, First",
                key="multi_tab_last_name",
            )

        with col2:
            destination = st.text_input(
                "Travel Destination",
                value="Budapest",
                help="Enter the destination city/country",
                key="multi_tab_destination",
            )

        st.markdown("<br>", unsafe_allow_html=True)

        xls_file_name = st.text_input(
            label="Enter name for output XLS file:",
            value="my_travel_expenses.xlsx",
            help="Provide a name for the output Excel file",
            key="multi_tab_xls_name",
        )

        if st.button(
            "⚡ Process Uploaded Files", type="primary", use_container_width=True
        ):
            if uploaded_files:
                # Save uploaded files to temp and collect their paths and names
                temp_dir = tempfile.mkdtemp()
                temp_paths, temp_names = [], []
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

                # Create the XLS output arguments with user input
                xls_args = XlsOutputArgs(
                    output_file=xls_file_name,
                    trip_metadata=TripMetadata(
                        last_first_name=last_first_name,
                        destination=destination,
                        location="Munich",
                        cost_center="100392",
                        reason_for_travel="Business Trip",
                    ),
                )

                # Initialize and run the Graph
                supervisor = ProcessorGraph(
                    list_of_files=temp_paths, xls_output_file_args=xls_args
                )

                with st.spinner("Processing your invoices... (please wait ⏱️)"):
                    result = asyncio.run(supervisor.ainvoke())

                # Store results using SessionStateManager
                SessionStateManager.set_multi_processing_results(
                    result, merged_pdf_path, xls_file_name
                )

            else:
                st.warning("⚠️ Please upload at least one file!")

        # Display results only if conditions are met
        if SessionStateManager.should_show_multi_results():
            st.markdown("---")

            # Display merged PDF and markdown result side by side
            col1, col2 = st.columns(2, gap="large")
            with col1:
                st.subheader("Original")
                with open(st.session_state.merged_pdf_path, "rb") as f:
                    merged_pdf_bytes = BytesIO(f.read())
                display_pdf(merged_pdf_bytes)
            with col2:
                st.subheader("Summary")
                st.markdown("<br>", unsafe_allow_html=True)
                st.markdown(
                    st.session_state.processing_result["summary"],
                    unsafe_allow_html=True,
                )

            st.toast(
                f"File: {st.session_state.xls_file_name} created!",
                icon="🎉",
            )
            st.snow()


# --------------------------
if __name__ == "__main__":
    main()
