FROM python:3.13-alpine
WORKDIR /SCAMPI
ENV PYTHONUNBUFFERED=1
RUN apk add --update --no-cache python3
# RUN apk add gcc libc-dev g++ libffi-dev libxml2 unixodbc-dev mariadb-dev

# Install dependencies
RUN apk --no-cache add curl gnupg
RUN apk add --no-cache gcc g++ musl-dev xz-dev


#Download the desired package(s)
RUN curl -O https://download.microsoft.com/download/0b3d5518-b4a7-4a2b-afc7-7ee9e967f93c/msodbcsql18_18.6.2.1-1_amd64.apk
RUN curl -O https://download.microsoft.com/download/cad0d30f-b9b1-4765-a011-81d8a66c8b8d/mssql-tools18_18.6.2.1-1_amd64.apk

#(Optional) Verify signature, if 'gpg' is missing install it using 'apk add gnupg':
RUN curl -O https://download.microsoft.com/download/0b3d5518-b4a7-4a2b-afc7-7ee9e967f93c/msodbcsql18_18.6.2.1-1_amd64.sig
RUN curl -O https://download.microsoft.com/download/cad0d30f-b9b1-4765-a011-81d8a66c8b8d/mssql-tools18_18.6.2.1-1_amd64.sig

RUN curl https://packages.microsoft.com/keys/microsoft.asc | gpg --import -
RUN gpg --verify msodbcsql18_18.6.2.1-1_amd64.sig msodbcsql18_18.6.2.1-1_amd64.apk
RUN gpg --verify mssql-tools18_18.6.2.1-1_amd64.sig mssql-tools18_18.6.2.1-1_amd64.apk

#Install the package(s)
RUN apk add --allow-untrusted msodbcsql18_18.6.2.1-1_amd64.apk
RUN apk add --allow-untrusted mssql-tools18_18.6.2.1-1_amd64.apk

RUN python3 -m venv venv
RUN ./venv/bin/pip install py7zr

# RUN apk add py3-pip
# RUN python3 -m ensurepip
# RUN python3 -m pip install --upgrade pip

RUN ./venv/bin/pip install --no-cache --upgrade pip setuptools
COPY . .

RUN ./venv/bin/pip install -r ./requirements.txt
CMD ["./venv/bin/python", "./process_engine.py"]
