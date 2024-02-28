FROM python:3.10-slim as base
FROM base as builder

RUN apt-get update && apt-get install -y git gcc

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY . /build
RUN pip install /build/

FROM base
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
RUN useradd --create-home oxn
RUN chown -R oxn /opt/venv
USER oxn
WORKDIR /home/oxn
ENTRYPOINT ["oxn"]
