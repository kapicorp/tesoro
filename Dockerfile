FROM deepmind/kapitan:0.27.4

USER root
WORKDIR /opt/venv/
COPY . /opt/venv/
RUN python -m venv /opt/venv && pip install --no-cache-dir -r requirements.txt

USER kapitan
ENTRYPOINT [ "/opt/venv/bin/python", "-m", "admiral" ]
