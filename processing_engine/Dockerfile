FROM alpine:3.14
WORKDIR /SCAMPI
ENV PYTHONUNBUFFERED=1
RUN apk add --update --no-cache python3 && ln -sf python3 /usr/bin/python
RUN python3 -m ensurepip
RUN pip3 install --no-cache --upgrade pip setuptools
COPY . .


RUN pip install -r ./requirements.txt
CMD ["python", "./source_extractor/source_extractor.py"]