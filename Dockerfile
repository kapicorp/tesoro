FROM deepmind/kapitan:0.29

USER root
WORKDIR /opt/venv/

COPY . /opt/venv/
RUN python -m venv /opt/venv && pip install --no-cache-dir -r requirements.txt

#USER kapitan see https://github.com/kapicorp/tesoro/issues/1
ENTRYPOINT [ "/opt/venv/bin/python", "-m", "tesoro" ]
