FROM vitasdk/vitasdk:latest

USER root

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install --yes --no-install-recommends \
        bzip2 \
        ca-certificates \
        curl \
        libgl1 \
        libwebp-dev \
        python3 \
        python3-pip \
        python3-venv \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-tools.txt /tmp/subahibi-requirements.txt
RUN python3 -m venv /opt/subahibi/venv \
    && /opt/subahibi/venv/bin/pip install --no-cache-dir \
        -r /tmp/subahibi-requirements.txt

COPY docker/fetch-vendors.sh /usr/local/bin/fetch-subahibi-vendors
RUN fetch-subahibi-vendors /opt/subahibi/vendor \
    && test -x "${VITASDK}/bin/vita-mksfoex" \
    && test -x "${VITASDK}/bin/vita-pack-vpk"

COPY docker/entrypoint.sh /usr/local/bin/subahibi

ENV PATH="/opt/subahibi/venv/bin:${PATH}" \
    SUBAHIBI_VENDOR_DIR=/opt/subahibi/vendor \
    SUBAHIBI_WEBP_LIBRARY=/usr/lib/x86_64-linux-gnu/libwebp.so

WORKDIR /workspace
ENTRYPOINT ["subahibi"]
CMD ["build"]
