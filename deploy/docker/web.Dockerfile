ARG WEB_BASE_IMAGE
FROM ${WEB_BASE_IMAGE}

USER root
COPY config/web-security-apk.txt /tmp/web-security-apk.txt
RUN xargs apk add --no-cache < /tmp/web-security-apk.txt \
    && rm /tmp/web-security-apk.txt
USER 101:101
