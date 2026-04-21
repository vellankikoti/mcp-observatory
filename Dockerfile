FROM python:3.11-slim AS builder
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY packages/sdk /app/packages/sdk
COPY packages/server /app/packages/server
COPY README.md ./
RUN pip install --prefix=/install ./packages/sdk ./packages/server

FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY --from=builder /install /usr/local
RUN useradd -m -u 10001 obs
USER 10001
ENTRYPOINT ["observatory-server"]
CMD ["--help"]
