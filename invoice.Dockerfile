FROM python:3.12-slim
EXPOSE 8080
WORKDIR /app
RUN pip install --no-cache-dir uv
COPY pyproject.toml /app/pyproject.toml

COPY .streamlit /app/.streamlit
COPY data /app/data
COPY app.py /app/streamlit_app.py
COPY src /app/src

RUN uv venv --python 3.12 && uv sync --no-cache
CMD ["uv", "run", "streamlit run streamlit_app.py --server.port=5000 --server.address=0.0.0.0"]