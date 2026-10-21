# Build stage
FROM golang:1.23-alpine AS builder

WORKDIR /app
COPY services/workflow-engine/go.mod services/workflow-engine/go.sum ./
RUN go mod download

COPY services/workflow-engine/ ./
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o /bin/workflow-engine ./cmd/server

# Production runtime stage
FROM alpine:3.20

RUN apk --no-cache add ca-certificates tzdata wget \
    && addgroup -S fieldkit && adduser -S fieldkit -G fieldkit

WORKDIR /app
COPY --from=builder /bin/workflow-engine /app/workflow-engine

USER fieldkit
EXPOSE 8008

HEALTHCHECK --interval=10s --timeout=5s --retries=3 \
    CMD wget -qO- http://localhost:8008/healthz || exit 1

ENTRYPOINT ["/app/workflow-engine"]
