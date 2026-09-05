# HardTech Hub Infrastructure

Este directorio contiene la base de infraestructura local para el MVP de HardTech Hub usando Docker Compose y LocalStack.

## Servicios incluidos

- PostgreSQL para `catalog-service`
- MySQL para `order-service`
- LocalStack con `S3` y `DynamoDB` para `analytics-service` e `identity-service`

## Estructura

- `docker-compose.yml`: orquestacion local de infraestructura
- `postgres/init/01_catalog.sql`: esquema inicial y semilla de catalogo
- `mysql/init/01_orders.sql`: esquema inicial y semilla de ordenes
- `localstack/init/01-bootstrap.sh`: crea bucket S3 y tabla DynamoDB
- `.env.example`: variables base sugeridas para los microservicios

## Levantar el entorno

```bash
docker compose -f infrastructure/docker-compose.yml up -d
```

## Servicios disponibles

- PostgreSQL: `localhost:5432`
- MySQL: `localhost:3306`
- LocalStack: `localhost:4566`

## Recursos creados automaticamente

- Bucket S3: `hardtech-datalake`
- Tabla DynamoDB: `users`
- GSI DynamoDB: `email-index`

## Siguiente paso

Conectar cada microservicio a estas dependencias usando las variables del archivo `.env.example`.
