# HardTech Hub

Plataforma inteligente para venta y configuración de componentes de PC.

## Arquitectura

Cinco microservicios independientes, tres lenguajes, persistencia políglota y pipeline de ingesta a S3.

```
React Front-End (AWS Amplify)
        │
        ▼
┌───────────────────────────────────────────────────┐
│  MS1 Identity   MS2 Catalog   MS3 Orders          │
│  Python:8001    TypeScript:8002  Python:8003       │
│  DynamoDB       PostgreSQL       MySQL             │
│                                                   │
│  MS4 Compatibility   MS5 Analytics                │
│  Go:8004             Python:8005                  │
│  Stateless           S3 (LocalStack)              │
└───────────────────────────────────────────────────┘
        │
        ▼
EC2 → Docker Ingestor → S3 hardtech-datalake
```

## Lenguajes por servicio

| Servicio | Lenguaje | Puerto |
|---|---|---|
| identity-service | Python (FastAPI) | 8001 |
| catalog-service | TypeScript (Fastify) | 8002 |
| order-service | Python (FastAPI) | 8003 |
| compatibility-service | Go (net/http) | 8004 |
| analytics-service | Python (FastAPI) | 8005 |

## Bases de datos

| Motor | Dominio |
|---|---|
| Amazon DynamoDB (LocalStack) | Usuarios, roles y preferencias |
| PostgreSQL | Catálogo, marcas y categorías |
| MySQL | Órdenes e ítems |
| Amazon S3 (LocalStack) | Data Lake de eventos de navegación |

## Requisitos

- Docker >= 24
- Docker Compose >= 2.20

## Levantar el entorno

```bash
# Primera vez: crear la red externa
docker network create hardtech-net

# Levantar toda la plataforma
docker compose up -d --build

# Ver logs del ingestor en tiempo real
docker logs -f proyecto-ingestor-1
```

Los servicios estarán disponibles en:

```
http://localhost:8001/docs   # Identity Service      (Swagger — FastAPI)
http://localhost:8002/docs   # Catalog Service       (Swagger — Fastify)
http://localhost:8003/docs   # Order Service         (Swagger — FastAPI)
http://localhost:8004/health # Compatibility Service
http://localhost:8005/docs   # Analytics Service (Swagger)
```

## Documentación de microservicios

---

### MS1 — Identity Service

| Campo | Valor |
|---|---|
| Lenguaje | Python 3.11 |
| Framework | FastAPI |
| Puerto | 8001 |
| Persistencia | Amazon DynamoDB (LocalStack) |
| Swagger | http://localhost:8001/docs |

**Responsabilidad:** gestiona el ciclo completo de identidad: registro, autenticación y consulta de perfil. Emite JWT firmados con bcrypt para hash de contraseñas.

**Tabla DynamoDB:** `users`

| Atributo | Tipo | Descripción |
|---|---|---|
| `user_id` | String (PK) | Identificador único (`usr_xxxx`) |
| `email` | String | Correo electrónico (GSI) |
| `password_hash` | String | Hash bcrypt de la contraseña |
| `roles` | List | `["customer"]` o `["admin"]` |
| `preferences` | Map | `{"currency":"PEN","theme":"dark"}` |
| `created_at` | String | ISO 8601 |

**Endpoints:**

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/health` | Estado del servicio |
| POST | `/api/auth/register` | Registrar nuevo usuario |
| POST | `/api/auth/login` | Autenticar y obtener JWT |
| GET | `/api/auth/me` | Perfil del usuario autenticado (Bearer token) |

**Usuario demo:** `demo@hardtech.com` / `password123`

---

### MS2 — Catalog Service

| Campo | Valor |
|---|---|
| Lenguaje | TypeScript (Node.js 20) |
| Framework | Fastify v4 |
| Puerto | 8002 |
| Persistencia | PostgreSQL 16 |
| Swagger | http://localhost:8002/docs |

**Responsabilidad:** dueño del catálogo comercial. Gestiona productos, marcas y categorías. Usa JSONB en PostgreSQL para almacenar especificaciones técnicas variables por tipo de componente.

**Esquema PostgreSQL:**

```
brands(id, name, country)
categories(id, name, description)
products(id, category_id, brand_id, sku, name, description,
         price, specs JSONB, image_url, is_active, created_at)
```

**Endpoints:**

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/health` | Estado del servicio |
| GET | `/api/products` | Listar productos activos |
| GET | `/api/products/:id` | Detalle de un producto |
| POST | `/api/products` | Crear producto |
| PUT | `/api/products/:id` | Actualizar producto |
| DELETE | `/api/products/:id` | Desactivar producto (soft delete) |

**Productos semilla:**

| ID | SKU | Nombre | Specs clave |
|---|---|---|---|
| 1 | CPU-AMD-7700X | AMD Ryzen 7 7700X | socket: AM5 |
| 2 | MB-ASUS-AM5-B650 | ASUS Prime B650 | socket: AM5, memory_type: DDR5 |
| 3 | GPU-NV-4070TI | NVIDIA GeForce RTX 4070 Ti | recommended_psu_watts: 700 |
| 4 | RAM-COR-DDR5-32 | Corsair Vengeance DDR5 32GB | memory_type: DDR5 |
| 5 | PSU-COR-RM850X | Corsair RM850x 850W | wattage: 850 |

---

### MS3 — Order Service

| Campo | Valor |
|---|---|
| Lenguaje | Python 3.11 |
| Framework | FastAPI |
| Puerto | 8003 |
| Persistencia | MySQL 8.0 |
| Swagger | http://localhost:8003/docs |

**Responsabilidad:** ciclo de vida de pedidos. Al crear una orden consulta `Catalog Service` para obtener el precio vigente y guarda un snapshot de `sku`, `name` y `unit_price`, preservando el historial aunque el catálogo cambie.

**Esquema MySQL:**

```
orders(id, user_id, status, subtotal, tax, shipping_cost, total_amount, created_at, updated_at)
order_items(id, order_id, product_id, product_sku, product_name, quantity, unit_price, subtotal)
```

**Endpoints:**

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/health` | Estado del servicio |
| POST | `/api/orders` | Crear pedido (consulta catálogo) |
| GET | `/api/orders/:id` | Detalle de pedido con ítems |
| GET | `/api/orders/user/:user_id` | Pedidos de un usuario |
| PATCH | `/api/orders/:id/status` | Actualizar estado |

**Estados:** `PENDING` → `PAID` → `SHIPPED` → `CANCELLED`

**Cálculo de totales:** subtotal + 18% IGV + S/ 25.00 envío fijo

---

### MS4 — Compatibility Service

| Campo | Valor |
|---|---|
| Lenguaje | Go 1.22 |
| Framework | net/http (stdlib) |
| Puerto | 8004 |
| Persistencia | Stateless (consulta MS2) |
| Swagger | http://localhost:8004/docs |
| OpenAPI JSON | http://localhost:8004/openapi.json |

**Responsabilidad:** valida compatibilidad entre componentes de hardware consultando especificaciones al `Catalog Service`. No tiene base de datos propia; aplica reglas en memoria.

**Reglas implementadas:**

| Regla | Componentes requeridos | Validación |
|---|---|---|
| `CPU_SOCKET` | cpu + motherboard | `CPU.specs.socket == Motherboard.specs.socket` |
| `RAM_TYPE` | ram + motherboard | `RAM.specs.memory_type == Motherboard.specs.memory_type` |
| `PSU_POWER` | psu + gpu | `PSU.specs.wattage >= GPU.specs.recommended_psu_watts` |

Las reglas se aplican automáticamente según los tipos de componentes recibidos. Se pueden enviar de 2 a 5 componentes en una sola llamada.

**Endpoints:**

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/health` | Estado del servicio |
| POST | `/api/compatibility/check` | Validar lista de componentes |
| GET | `/openapi.json` | Spec OpenAPI 3.0 en JSON |
| GET | `/docs` | Swagger UI |

---

### MS5 — Analytics Service

| Campo | Valor |
|---|---|
| Lenguaje | Python 3.11 |
| Framework | FastAPI |
| Puerto | 8005 |
| Persistencia | Amazon S3 (LocalStack) |
| Swagger | http://localhost:8005/docs |

**Responsabilidad:** expone métricas de comportamiento de usuarios a partir de eventos almacenados en S3. Lee archivos JSON particionados por fecha con boto3. En arquitectura objetivo se reemplaza la lectura directa por consultas Athena.

**Estructura del Data Lake:**

```
s3://hardtech-datalake/
  raw/events/year=YYYY/month=MM/day=DD/events_HHMMSS_xxxxxx.json
```

**Schema de evento:**

| Campo | Tipo | Ejemplo |
|---|---|---|
| `event_id` | string | `evt_a1b2c3d4` |
| `timestamp` | ISO 8601 | `2026-09-05T10:00:00Z` |
| `user_id` | string | `usr_007` |
| `event_type` | enum | `PRODUCT_VIEW` |
| `product_id` | integer / null | `1` |
| `category` | string | `CPU` |
| `session_id` | string | `sess_x9y8z7` |

**Tipos de evento:** `PRODUCT_VIEW`, `PRODUCT_SEARCH`, `ADD_TO_CART`, `REMOVE_FROM_CART`, `ORDER_CREATED`

**Endpoints:**

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/health` | Estado del servicio |
| GET | `/api/analytics/events/count` | Total y conteo por tipo de evento |
| GET | `/api/analytics/top-products` | Top productos por visualizaciones |

---

## Endpoints principales

### Identity Service — Python :8001

```bash
# Registrar usuario
curl -X POST http://localhost:8001/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"nuevo@hardtech.com","password":"password123"}'

# Login
curl -X POST http://localhost:8001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"demo@hardtech.com","password":"password123"}'

# Perfil autenticado
curl http://localhost:8001/api/auth/me \
  -H "Authorization: Bearer <token>"
```

### Catalog Service — TypeScript :8002

```bash
# Listar productos
curl http://localhost:8002/api/products

# Detalle de producto
curl http://localhost:8002/api/products/1

# Crear producto (admin)
curl -X POST http://localhost:8002/api/products \
  -H "Content-Type: application/json" \
  -d '{"category_id":1,"brand_id":1,"sku":"CPU-TEST","name":"Test CPU","price":999.90,"specs":{"socket":"AM5"}}'
```

Catálogo actual:

| ID | SKU | Producto |
|---|---|---|
| 1 | CPU-AMD-7700X | AMD Ryzen 7 7700X |
| 2 | MB-ASUS-AM5-B650 | ASUS Prime B650 |
| 3 | GPU-NV-4070TI | NVIDIA GeForce RTX 4070 Ti |
| 4 | RAM-COR-DDR5-32 | Corsair Vengeance DDR5 32GB |
| 5 | PSU-COR-RM850X | Corsair RM850x 850W |

### Order Service — Python :8003

```bash
# Crear pedido
curl -X POST http://localhost:8003/api/orders \
  -H "Content-Type: application/json" \
  -d '{"user_id":"usr_demo_001","items":[{"product_id":1,"quantity":1}]}'

# Consultar pedido
curl http://localhost:8003/api/orders/1

# Pedidos por usuario
curl http://localhost:8003/api/orders/user/usr_demo_001

# Actualizar estado
curl -X PATCH http://localhost:8003/api/orders/1/status \
  -H "Content-Type: application/json" \
  -d '{"status":"PAID"}'
```

Estados válidos: `PENDING` → `PAID` → `SHIPPED` → `CANCELLED`

### Compatibility Service — Go :8004

```bash
# Validar build completo (CPU + MB + RAM + GPU + PSU)
curl -X POST http://localhost:8004/api/compatibility/check \
  -H "Content-Type: application/json" \
  -d '{
    "components": [
      {"type": "cpu",         "product_id": 1},
      {"type": "motherboard", "product_id": 2},
      {"type": "ram",         "product_id": 4},
      {"type": "gpu",         "product_id": 3},
      {"type": "psu",         "product_id": 5}
    ]
  }'
```

Reglas implementadas:

| Regla | Validación |
|---|---|
| CPU_SOCKET | CPU.socket == Motherboard.socket |
| RAM_TYPE | RAM.memory_type == Motherboard.memory_type |
| PSU_POWER | PSU.wattage >= GPU.recommended_psu_watts |

### Analytics Service — Python :8005

```bash
# Conteo de eventos por tipo
curl http://localhost:8005/api/analytics/events/count

# Top productos por visualizaciones
curl http://localhost:8005/api/analytics/top-products
```

## Health checks

```bash
for port in 8001 8002 8003 8004 8005; do
  echo -n "Port $port: "
  curl -s http://localhost:$port/health
  echo ""
done
```

## Pipeline de ingesta

El contenedor `ingestor` genera 10 eventos cada 30 segundos y los sube a S3:

```
s3://hardtech-datalake/raw/events/year=YYYY/month=MM/day=DD/events_HHMMSS_xxxxxx.json
```

```bash
# Ver logs del ingestor
docker logs -f proyecto-ingestor-1

# Listar archivos en S3
docker exec proyecto-localstack-1 awslocal s3 ls s3://hardtech-datalake/raw/events/ --recursive

# Ver contenido de un archivo
docker exec proyecto-localstack-1 awslocal s3 cp \
  s3://hardtech-datalake/raw/events/year=2026/month=09/day=05/events_001.json -
```

Tipos de evento: `PRODUCT_VIEW`, `PRODUCT_SEARCH`, `ADD_TO_CART`, `REMOVE_FROM_CART`, `ORDER_CREATED`

## Estructura del repositorio

```
hardtech-hub/
├── services/
│   ├── identity-service/       # Python + FastAPI + DynamoDB
│   ├── catalog-service/        # TypeScript + Fastify + PostgreSQL
│   ├── order-service/          # Python + FastAPI + MySQL
│   ├── compatibility-service/  # Go + net/http (stateless)
│   └── analytics-service/      # Python + FastAPI + S3
├── ingestion/
│   ├── ingest.py               # Generador de eventos + upload S3
│   ├── Dockerfile
│   └── requirements.txt
├── infrastructure/
│   ├── postgres/init/          # Schema y seed del catálogo
│   ├── mysql/init/             # Schema y seed de órdenes
│   └── localstack/init/        # Bootstrap DynamoDB + S3
├── docker-compose.yml
└── README.md
```

## Variables de entorno clave

| Variable | Servicio | Valor por defecto |
|---|---|---|
| `DYNAMODB_ENDPOINT` | identity | `http://localstack:4566` |
| `CATALOG_SERVICE_URL` | order, compatibility | `http://catalog-service:8002` |
| `S3_ENDPOINT_URL` | analytics, ingestor | `http://localstack:4566` |
| `S3_BUCKET` | analytics, ingestor | `hardtech-datalake` |
| `INTERVAL_SECONDS` | ingestor | `30` |
| `BATCH_SIZE` | ingestor | `10` |
