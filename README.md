# MSc Dissertation Testbed – Bookstore Microservices & Diagnostic Agent

A microservices-based bookstore testbed built for the MSc Advanced Computer Science dissertation at Newcastle University. The repository contains two main components:
- **Testbed**: Spring Boot microservices, PostgreSQL, and a Python load generator for resilience and fault-injection experiments.
- **Diagnostic Agent**: A LangGraph-based ReAct agent (in `Agent_Impl/`) that diagnoses faults under two observability conditions.

## Table of Contents
- [Overview](#overview)
- [Architecture](#architecture)
- [Services & Responsibilities](#services--responsibilities)
- [Observability Conditions](#observability-conditions)
- [Fault Injection & Catalog](#fault-injection--catalog)
- [Tech Stack](#tech-stack)
- [Quick Start (Docker Compose)](#quick-start-docker-compose)
- [Local Build & Test](#local-build--test)
- [Kubernetes Deployment (Minikube)](#kubernetes-deployment-minikube)
- [Load Generator](#load-generator)
- [Diagnostic Agent](#diagnostic-agent)
- [API Surface](#api-surface)
- [Configuration](#configuration)
- [Repository Layout](#repository-layout)

## Overview
The testbed models a simple bookstore with inventory, ordering, and payments. It is designed to be small enough to run locally, yet rich enough to study microservice interactions, reliability patterns, and system behavior under faults. The diagnostic agent automates fault investigation using Kubernetes and/or Actuator telemetry.

## Architecture
- **Inventory Service** manages book catalog and stock.
- **Order Service** orchestrates reservations and payment authorization.
- **Payment Service** handles payment authorization requests.
- **PostgreSQL** provides separate databases for inventory and orders.
- **Load Generator** continuously browses catalog items and places orders.
- **Fault Injection** endpoints enable controlled failure scenarios.

## Services & Responsibilities
| Service | Port | Purpose |
| --- | --- | --- |
| Inventory Service | 8081 | Product catalog, stock management, reservations |
| Order Service | 8082 | Order creation and lookup, orchestration |
| Payment Service | 8083 | Payment authorization |
| PostgreSQL | 5432 | Inventory + Orders databases |

## Observability Conditions
Two experiment conditions are supported:
- **Condition A (Generic Infrastructure Observability)**: Kubernetes pod health, Metrics Server usage, pod events, and filtered application logs.
- **Condition B (Framework-Native Observability)**: Spring Boot Actuator health/metrics and Resilience4j circuit breaker telemetry, plus logs.

The Kubernetes manifests set `SPRING_PROFILES_ACTIVE=condition-a` (or `condition-b`) to control logging visibility for each condition.

## Fault Injection & Catalog
Faults are toggled via internal endpoints:
- `GET /internal/fault`
- `POST /internal/fault/activate/{faultId}`
- `POST /internal/fault/deactivate/{faultId}`

Fault catalog:
| Fault ID | Service | Description |
| --- | --- | --- |
| f1 | inventory-service | Starves the Hikari connection pool by holding connections |
| f2 | inventory-service | CPU saturation via intensive worker threads |
| f3 | payment-service | Forced payment authorization failures (HTTP 500) |
| f4 | inventory-service | Tomcat thread pool exhaustion by blocking requests |
| f5 | inventory-service | Slow heap memory leak and sustained pressure |
| f6 | inventory-service | Off-heap spike to trigger Kubernetes OOMKill |

These endpoints are intended for controlled experimentation and should not be exposed publicly.

## Tech Stack
- Java 25 + Spring Boot 3.5
- PostgreSQL 16
- Maven (multi-module build)
- Flyway migrations with seeded inventory data
- Resilience4j for circuit breakers (order-service)
- Docker Compose + Minikube/Kubernetes
- Python 3.12 load generator and diagnostic agent
- LangGraph + LangChain tools for the agent

## Quick Start (Docker Compose)
Run everything locally using Docker Compose and the Taskfile.

**Prerequisites:** Docker, Task, and a JDK (for building images).

```bash
cd Testbed

task start_infra   # starts PostgreSQL

task start         # builds images and starts services
```

Stop the stack:

```bash
task stop
```

Services will be available at:
- Inventory: http://localhost:8081
- Orders: http://localhost:8082
- Payments: http://localhost:8083

## Local Build & Test
**Testbed (Java)**
```bash
cd Testbed

task test
# or
bash ./mvnw clean verify
```

**Diagnostic Agent (Python)**
```bash
cd Agent_Impl
python -m pip install -r requirements.txt
pytest -m "not integration"
```

Integration tests require a running Minikube cluster with NodePorts exposed and a valid `kubectl` context:
```bash
pytest -m integration
```

## Kubernetes Deployment (Minikube)
Start Minikube and deploy the stack:

```bash
cd Testbed

task kube_start

task k8s_start
```

Services are exposed via NodePorts:
- Inventory: http://localhost:30081
- Orders: http://localhost:30082
- Payments: http://localhost:30083

Check status / teardown:

```bash
task k8s_status

task k8s_stop

task kube_stop
```

## Load Generator
The load generator continuously browses products and places orders.

Run locally:

```bash
cd Testbed/load-generator
python loadgen.py
```

Environment variables:
- `INVENTORY_URL` (default: `http://inventory-service:8081/api/products`)
- `ORDER_URL` (default: `http://order-service:8082/api/orders`)
- `BROWSE_INTERVAL` (default: `0.2` seconds)
- `ORDER_INTERVAL` (default: `2.0` seconds)

A pre-built container is also deployed by the Kubernetes manifests.

## Diagnostic Agent
The diagnostic agent (`Agent_Impl/`) is a LangGraph-based ReAct agent designed to diagnose faults in the microservices testbed.

**Prerequisites**
- Minikube cluster running with NodePorts exposed
- `kubectl` context pointing at the Minikube cluster
- LM Studio (or any OpenAI-compatible endpoint) running locally

**Install dependencies**
```bash
cd Agent_Impl
python -m pip install -r requirements.txt
```

**Run the smoke test**
```bash
python smoke_test.py --condition B
```

**Agent environment variables**
- `LM_STUDIO_BASE_URL` (default: `http://localhost:1234/v1`)
- `LM_STUDIO_API_KEY` (default: `lm-studio`)
- `MODEL_NAME` (default: `qwen/qwen3.5-9b_Paritosh`)
- `MODEL_TEMPERATURE` (default: `0.2`)
- `INVENTORY_BASE_URL` (default: `http://127.0.0.1:30081`)
- `ORDER_BASE_URL` (default: `http://127.0.0.1:30082`)
- `PAYMENT_BASE_URL` (default: `http://127.0.0.1:30083`)

## API Surface
### Inventory Service
- `GET /api/products` (supports filtering by `query`, `genre`, `author`, `name`, `isbn`, `minPrice`, `maxPrice`, `pageNo`)
- `GET /api/products/{code}`
- `POST /api/products`
- `PUT /api/products/{code}`
- `PATCH /api/products/{code}/price`
- `PATCH /api/products/{code}/stock`
- `POST /api/products/reservations`
- `POST /api/products/commit`
- `POST /api/products/release`

### Order Service
- `POST /api/orders`
- `GET /api/orders/{orderNumber}`
- `GET /api/orders/customer/{customerId}`

### Payment Service
- `POST /api/payments/authorizations`

## Configuration
Common environment variables:
- `DB_URL`, `DB_USERNAME`, `DB_PASSWORD` (inventory + orders)
- `ORDER_INVENTORY_SERVICE_URL` (order service)
- `ORDER_PAYMENT_SERVICE_URL` (order service)
- `SPRING_PROFILES_ACTIVE` (`condition-a`, `condition-b`, or `docker`)

Default ports:
- Inventory: **8081**
- Orders: **8082**
- Payments: **8083**

Actuator health checks are enabled (e.g. `/actuator/health/liveness`, `/actuator/health/readiness`).

## Repository Layout
```
.
├── Agent_Impl/                 # Diagnostic agent implementation + tests
├── Testbed/                    # Microservice system
│   ├── inventory-service/
│   ├── order-service/
│   ├── payment-service/
│   ├── load-generator/
│   ├── deployment/
│   │   ├── docker-compose/
│   │   └── kubernetes/
│   └── Taskfile.yml
└── README.md
```
