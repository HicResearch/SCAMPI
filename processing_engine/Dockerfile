FROM python:3.13-slim-bookworm
WORKDIR /SCAMPI
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential ca-certificates curl gnupg libgl1 libglib2.0-0 libgomp1 \
    liblzma-dev tesseract-ocr tesseract-ocr-eng unixodbc-dev \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://packages.microsoft.com/keys/microsoft.asc \
    | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/microsoft-prod.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" \
    > /etc/apt/sources.list.d/microsoft-prod.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 mssql-tools18 \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv venv
RUN ./venv/bin/pip install py7zr
RUN ./venv/bin/pip install --no-cache --upgrade pip setuptools
COPY . .

RUN ./venv/bin/pip install -r ./requirements.txt
RUN ./venv/bin/python -m spacy download en_core_web_lg
CMD ["./venv/bin/python", "./process_engine.py"]
