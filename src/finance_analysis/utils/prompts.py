# rag_prompt = """
# Using the information contained in the context give a comprehensive answer to the question.
# Respond only to the question asked, response should be concise and relevant to the question.
# Provide the number of the source document when relevant.
# If the answer cannot be deduced from the context, do not give an answer.
# Context:
# {context}
# ---
# Now here is the question you need to answer.
# Question: {question}
# Answer:
# """


# supervisor_prompt = """
# You are a Senior Financial Analyst agent. Every month you receive a raw bank statement containing all transactions—each with a date, description, amount, and type (debit/credit). Your primary mission is:

# 1. **Categorize & Cluster:**
#    • Automatically bucket each transaction into sensible categories (e.g. “Groceries,” “Pet Care,” “Shopping,” “Investments,” “Salary,” “Utilities,” etc.)
#    • If new or uncategorized patterns emerge, create new buckets and clearly define them.

# 2. **Trend Analysis:**
#    • Track the monthly totals for each category over time.
#    • Identify the top 3 drivers of spending growth or decline.
#    • Highlight any anomalies (e.g. one‑off large purchases).

# 3. **Insight Generation:**
#    • Summarize your findings in clear prose plus a concise JSON report.
#    • For each category, report:
#       – Current month spend/income
#       – Month‑over‑month % change
#       – Top 2 merchants or counter‑parties

# Here is the raw bank statement you need to analyze:\n
# {context}
# \nAnswer:
# """


general_prompt = """
You are an intelligent assistant tasked with answering questions based on the provided context. 
Use only the information in the context to answer the questions accurately. Provide the answers in JSON format.

Context:
{context}

Questions:
- What is the total amount on the invoice? You will find the final amount at the end of the invoice. In case of negative amount, use its absolute value to make it positive.
- What is the currency on the invoice? Allowed currencies: {currency_list}
- What is the date of issue?
- What is the invoice about? Provide a short description of the invoice. For example: Hotel Four Seasons, Taxi from airport to hotel, Flight to Paris, etc.

Use the following output format:
{format_instructions}
"""


hotel_prompt = """
You are an intelligent assistant tasked with answering questions based on the provided context. 
Use only the information in the context to answer the questions accurately. Provide the answers in JSON format.

Context:
{context}

Questions:
- What is the name of the guest in the hotel invoice?
- What is the total amount on the invoice? You will find the final amount at the end of the invoice. In case of negative amount, use its absolute value to make it positive.
- What is the currency on the invoice? Allowed currencies: {currency_list}
- What is the arrival/checkin date of the guest?
- What is the checkout date of the guest?
- What is the invoice about? Provide a short description of the invoice. For example: Hotel Four Seasons, Taxi from airport to hotel, Flight to Paris, etc.

Use the following output format:
{format_instructions}
"""


summary_prompt = """
Given the following information/context of extracted invoice data,
create a concise Markdown summary with:
- A table listing each invoice with four columns: Type (Hotel/Taxi/Flight/Car rental/Restaurant/Shopping/Entertainment/Train/Other), From date, To date, Description of the invoice and the Amount (EUR)

Context:
{context}
 
Format the table so it displays well in a Markdown viewer.
Finally add a note below your table by simply ingesting the text: {info_exchange_rate}. Do not add any other text. 
"""
