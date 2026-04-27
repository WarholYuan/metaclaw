FROM python:3.10-slim-bullseye

ARG INSTALL_BROWSER=true
ARG USE_CN_MIRROR=false

ENV BUILD_PREFIX=/app
ENV METACLAW_WORKSPACE=/home/agent/metaclaw
ENV PLAYWRIGHT_BROWSERS_PATH=/app/ms-playwright

WORKDIR ${BUILD_PREFIX}

RUN if [ "$USE_CN_MIRROR" = "true" ]; then \
        sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list; \
        pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple/; \
    fi

COPY . ${BUILD_PREFIX}

RUN apt-get update \
    && apt-get install -y --no-install-recommends bash ffmpeg espeak libavcodec-extra \
    && cp config-template.json config.json \
    && python -m pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir -r requirements-optional.txt \
    && pip install --no-cache-dir -e . \
    && if [ "$INSTALL_BROWSER" = "true" ]; then \
        apt-get install -y --no-install-recommends fonts-wqy-zenhei \
        && pip install --no-cache-dir "playwright==1.52.0" \
        && python -m playwright install-deps chromium \
        && mkdir -p /app/ms-playwright \
        && if [ "$USE_CN_MIRROR" = "true" ]; then \
            PLAYWRIGHT_DOWNLOAD_HOST=https://registry.npmmirror.com/-/binary/playwright \
            python -m playwright install chromium; \
        else \
            python -m playwright install chromium; \
        fi; \
    fi \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -r agent \
    && useradd -r -g agent -s /bin/bash -d /home/agent agent \
    && mkdir -p /home/agent/metaclaw \
    && chown -R agent:agent /home/agent ${BUILD_PREFIX} /usr/local/lib

COPY docker/entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh \
    && chown agent:agent /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
