FROM python:3.11-slim
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
ENV LLM_PROVIDER=stub DB_PATH=/srv/data/poc.db
RUN mkdir -p /srv/data
EXPOSE 8000
CMD ["uvicorn", "app.main:build_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
