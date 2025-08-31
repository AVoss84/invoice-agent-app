import streamlit as st
from finance_analysis.utils.utils import (
    get_logger,
)

logger = get_logger()


class SessionStateManager:
    """Manages Streamlit session state for the invoice processing app"""

    # Define default values for session state variables
    DEFAULTS = {
        "file_path": None,
        "markdown": None,
        "document": None,
        "active_tab": None,
        "multi_tab_processed": False,
        "processing_result": None,
        "merged_pdf_path": None,
        "xls_file_name": None,
        "show_upload_results": False,
        "show_multi_results": False,
        "last_uploaded_file": None,
        "temp_dir": None,
    }

    # Define groups of related session state variables
    UPLOAD_TAB_VARS = [
        "file_path",
        "markdown",
        "document",
        "show_upload_results",
    ]
    MULTI_TAB_VARS = [
        "multi_tab_processed",
        "processing_result",
        "merged_pdf_path",
        "xls_file_name",
        "show_multi_results",
        "temp_dir",
    ]

    @staticmethod
    def initialize() -> None:
        """Initialize all session state variables with default values if they don't exist"""
        for key, default_value in SessionStateManager.DEFAULTS.items():
            if key not in st.session_state:
                st.session_state[key] = default_value

    @staticmethod
    def clear_upload_tab_data() -> None:
        """Clear all session state data related to the upload tab"""
        for var in SessionStateManager.UPLOAD_TAB_VARS:
            st.session_state[var] = SessionStateManager.DEFAULTS[var]

    @staticmethod
    def clear_multi_tab_data() -> None:
        """Clear all session state data related to the multi-file processing tab"""
        for var in SessionStateManager.MULTI_TAB_VARS:
            st.session_state[var] = SessionStateManager.DEFAULTS[var]

    @staticmethod
    def switch_to_upload_tab() -> None:
        """Handle switching to the upload tab - clear multi-tab data and set active tab"""
        if st.session_state.active_tab != "upload":
            st.session_state.active_tab = "upload"
            SessionStateManager.clear_multi_tab_data()

    @staticmethod
    def switch_to_multi_tab() -> None:
        """Handle switching to the multi-file tab - clear upload data and set active tab"""
        if st.session_state.active_tab != "multi":
            st.session_state.active_tab = "multi"
            SessionStateManager.clear_upload_tab_data()

    @staticmethod
    def set_upload_results(
        file_path: str, markdown: str, document: object, show_results: bool = True
    ) -> None:
        """Set the results from document processing"""
        st.session_state.file_path = file_path
        st.session_state.markdown = markdown
        st.session_state.document = document
        st.session_state.show_upload_results = show_results

    @staticmethod
    def set_multi_processing_results(
        result: dict, merged_pdf_path: str, xls_file_name: str
    ) -> None:
        """Set the results from multi-file processing"""
        st.session_state.processing_result = result
        st.session_state.merged_pdf_path = merged_pdf_path
        st.session_state.xls_file_name = xls_file_name
        st.session_state.multi_tab_processed = True
        st.session_state.show_multi_results = True

    @staticmethod
    def reset_multi_processing() -> None:
        """Reset multi-processing state for new processing"""
        SessionStateManager.clear_multi_tab_data()
        st.rerun()

    @staticmethod
    def reset_upload_tab() -> None:
        """Reset upload tab state for new file upload"""
        SessionStateManager.clear_upload_tab_data()
        # Also clear the last uploaded file to allow reprocessing
        st.session_state.last_uploaded_file = None
        st.rerun()

    @staticmethod
    def should_show_upload_results() -> bool:
        """Check if upload results should be displayed"""
        return (
            st.session_state.show_upload_results
            and st.session_state.markdown
            and st.session_state.active_tab == "upload"
        )

    @staticmethod
    def should_show_multi_results() -> bool:
        """Check if multi-processing results should be displayed"""
        return (
            st.session_state.show_multi_results
            and st.session_state.processing_result
            and st.session_state.merged_pdf_path
            and st.session_state.active_tab == "multi"
        )

    @staticmethod
    def get_state_info() -> dict:
        """Get current state information for debugging"""
        return {
            "active_tab": st.session_state.active_tab,
            "upload_results": st.session_state.show_upload_results,
            "multi_results": st.session_state.show_multi_results,
            "multi_processed": st.session_state.multi_tab_processed,
            "has_markdown": st.session_state.markdown is not None,
            "has_processing_result": st.session_state.processing_result is not None,
        }
