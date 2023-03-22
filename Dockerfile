FROM python:3.11-slim AS builder


USER root

RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        build-essential \
        libffi-dev \
        libmagic1


ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

WORKDIR /opt/venv/

COPY . /opt/venv/

RUN pip install -r requirements.txt

FROM python:3.11-slim

COPY --from=builder /opt/venv /opt/venv
USER root
WORKDIR /opt/venv/

RUN apt-get update \
    && apt-get install -y libmagic1

ENV VIRTUAL_ENV=/opt/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
#USER kapitan see https://github.com/kapicorp/tesoro/issues/1
ENTRYPOINT [ "python", "-m", "tesoro" ]
