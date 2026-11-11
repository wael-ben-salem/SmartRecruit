FROM python:3.12-slim
WORKDIR /app/api
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY smartrecruit ./smartrecruit
EXPOSE 8000
CMD ["uvicorn", "smartrecruit.main:app", "--host", "0.0.0.0", "--port", "8000"]
