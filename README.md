# Invoice Agent App

This application simplifies the reimbursement process for business trip invoices. It automates the workflow from scanned PDF invoices to a ready-to-submit Excel file required for reimbursement. It uses a Multi-Agent system built in LangGraph. The extraction pipeline supports two processing modes: a classic OCR-first flow with Google Document AI and a direct multimodal flow with Gemini 2.5 Flash. The default mode is direct multimodal extraction.


## Project structure

```
├── app.py
├── data
├── docker-compose.yaml
├── invoice.Dockerfile
├── Makefile
├── pyproject.toml
├── README.md
├── src
│   ├── finance_analysis
│   │   ├── config
│   │   ├── resources
│   │   ├── services
│   │   └── utils
│   └── notebooks
├── tests
```

## Agent Graph

Below is a visualization of the agent graph used in the app:

![Invoice Agent Graph](data/invoice_graph.png)

## How it works

1. **Drop your scanned PDFs** into a folder.
2. The app **processes each file**:
   - Merges PDFs if needed
   - Runs either OCR-first extraction or direct multimodal extraction depending on `OCR_MODE`
   - Extracts text and key fields using AI models
   - Classifies the invoice type (hotel, taxi, flight, etc.)
3. **All extracted data is summarized** and mapped to the correct fields.
4. The app **fills out the official reimbursement Excel template** with all required details.

## OCR vs multimodality

The app supports two document-processing strategies.

- `gemini_direct`: Sends the original PDF or image directly to Gemini 2.5 Flash in a single multimodal call. Gemini classifies the document and extracts the invoice fields in one step. This is the current default and works well for visually complex files such as email-style receipts or PDFs where OCR quality is poor.
- `documentai`: First runs Google Document AI to create OCR text, then uses the downstream classifier and extractor on the processed text. This can still be useful for documents where a text-first pipeline is preferred.

Current default:

```python
OCR_MODE = "gemini_direct"
```

Location:

- [src/finance_analysis/config/global_config.py](/Users/avosseler/Github_priv/invoice-agent-app/src/finance_analysis/config/global_config.py)

Behavior:

- In `gemini_direct` mode, the app skips the separate OCR-to-classification step and directly returns structured invoice fields.
- In `documentai` mode, the app keeps the OCR-first pipeline and classifies based on the extracted text.

When to use which mode:

- Use `gemini_direct` for mixed-layout invoices, screenshots, Booking.com receipts, ESTA confirmations, and other visually structured PDFs.
- Use `documentai` if you explicitly want a text-first OCR pipeline or need to compare OCR output against multimodal extraction.

## Usage

1. **Upload your invoices** as PDF files through the app interface
2. **Enter trip information** (name, destination, etc.)
3. **Click "Process Uploaded Files"** to start the AI processing
4. **Download the results:**
   - A pre-filled Excel reimbursement file with all expense details
   - A merged PDF containing all uploaded invoices in the order listed in the Excel file
5. **Review and edit** the downloaded files if needed
6. **Finalize your submission:**
   - Save the Excel file as PDF
   - Merge it on top of the generated PDF (Excel PDF first, then invoice PDFs)
   - Submit the complete package

## Getting started

Create a virtual environment:
```bash
uv venv --python 3.12
uv sync
```

Start the app:
```bash
make ui       
```

Switch processing mode by setting `OCR_MODE` in [src/finance_analysis/config/global_config.py](/Users/avosseler/Github_priv/invoice-agent-app/src/finance_analysis/config/global_config.py):

```python
OCR_MODE = "gemini_direct"  # or "documentai"
```

Format code:
```bash
make format
```

## Business context

- **Goal:** Automate and accelerate the reimbursement process for business travel expenses.
- **Input:** Scanned PDF invoices from various sources.
- **Output:** Ready-to-submit Excel file for your company's reimbursement workflow.
- **Impact:** Saves time, reduces manual errors, and streamlines the process for employees and finance teams.

