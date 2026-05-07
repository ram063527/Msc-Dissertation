# MSc Dissertation Testbed – Bookstore Microservices

A microservices-based bookstore testbed built for the MSc Advanced Computer Science dissertation at Newcastle University. The system simulates a small e-commerce platform and provides a realistic distributed environment for resilience, observability, and fault-injection research. A diagnostic agent is located in the `Agent_Impl/` directory.

## Table of Contents
- [Overview](#overview)
- [Architecture](#architecture)
- [Services & Responsibilities](#services--responsibilities)
- [Tech Stack](#tech-stack)
- [Quick Start (Docker Compose)](#quick-start-docker-compose)
- [Local Build & Test](#local-build--test)
- [Kubernetes Deployment (Minikube)](#kubernetes-deployment-minikube)
- [Load Generator](#load-generator)
- [Diagnostic Agent](#diagnostic-agent)
- [API Surface](#api-surface)
- [Fault Injection](#fault-injection)
- [Configuration](#configuration)
- [Repository Layout](#repository-layout)

## Overview
The testbed models a simple bookstore with inventory, ordering, and payments. It is designed to be small enough to run locally, yet rich enough to study microservice interactions, reliability patterns, and system behavior under faults.

## Architecture
- **Inventory Service** manages book catalog and stock.
- **Order Service** orchestrates reservations and payment authorization.
- **Payment Service** handles payment authorization requests.
- **PostgreSQL** provides separate databases for inventory and orders.
- **Load Generator** continuously browses catalog items and places orders.
- **Fault Injection** endpoints allow toggling controlled failures (inventory/payment).

## Services & Responsibilities
| Service | Port | Purpose |
| --- | --- | --- |
| Inventory Service | 8081 | Product catalog, stock management, reservations |
| Order Service | 8082 | Order creation and lookup, orchestration |
| Payment Service | 8083 | Payment authorization |
| PostgreSQL | 5432 | Inventory + Orders databases |

## Tech Stack
- Java 25 + Spring Boot
- PostgreSQL 16
- Maven (multi-module build)
- Flyway migrations with seeded inventory data
- Resilience4j for circuit breakers
- Docker Compose + Minikube/Kubernetes
- Python load generator

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
From the `Testbed` directory:

```bash
task test
```

Or directly with Maven wrapper:

```bash
./mvnw clean verify
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
The diagnostic agent (`Agent_Impl/`) is a LangGraph-based ReAct agent designed to diagnose faults in the microservices testbed. It supports two observability conditions:
- **Condition A**: Generic logs and resource metrics.
- **Condition B**: Deep framework-native observability via Spring Boot Actuator.

To run the agent smoke test:
```bash
cd Agent_Impl
python smoke_test.py --condition B
```

## API Surface
### Inventory Service
- `GET /api/products`
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

## Fault Injection
Inventory and Payment services expose internal fault controls:
- `GET /internal/fault`
- `POST /internal/fault/activate/{faultId}`
- `POST /internal/fault/deactivate/{faultId}`

These endpoints are intended for controlled experimentation and should not be exposed publicly.

## Configuration
Common environment variables:
- `DB_URL`, `DB_USERNAME`, `DB_PASSWORD` (inventory + orders)
- `ORDER_INVENTORY_SERVICE_URL` (order service)
- `ORDER_PAYMENT_SERVICE_URL` (order service)
- `SPRING_PROFILES_ACTIVE` (condition profiles used by the test harness)

Default ports:
- Inventory: **8081**
- Orders: **8082**
- Payments: **8083**

Actuator health checks are enabled (e.g. `/actuator/health/liveness`, `/actuator/health/readiness`).

## Repository Layout
```
.
├── Agent_Impl/                 # Diagnostic agent implementation
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
