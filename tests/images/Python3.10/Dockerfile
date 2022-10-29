FROM python:3.10-alpine

RUN adduser --disabled-password sandbox && \
    mkdir /sandbox && \
    chown sandbox:sandbox /sandbox

WORKDIR /sandbox

CMD ["python", "main.py"]