#!/bin/bash
set -euo pipefail

echo "Creating S3 bucket and DynamoDB table in LocalStack..."

awslocal s3 mb s3://hardtech-datalake || true

awslocal dynamodb create-table \
  --table-name users \
  --attribute-definitions \
    AttributeName=user_id,AttributeType=S \
    AttributeName=email,AttributeType=S \
  --key-schema AttributeName=user_id,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --global-secondary-indexes '[{"IndexName":"email-index","KeySchema":[{"AttributeName":"email","KeyType":"HASH"}],"Projection":{"ProjectionType":"ALL"}}]' \
  || true

awslocal dynamodb put-item \
  --table-name users \
  --item '{
    "user_id": {"S": "usr_demo_001"},
    "email": {"S": "demo@hardtech.com"},
    "password_hash": {"S": "$2b$12$5RHTUV9lTrB4FG4pLeKZr.hJbaLC20XlD0UaIxN.Lo0Fx0FLnv8ty"},
    "roles": {"L": [{"S": "customer"}]},
    "preferences": {"M": {"currency": {"S": "PEN"}, "theme": {"S": "dark"}}},
    "created_at": {"S": "2026-09-02T10:00:00Z"}
  }' \
  || true

echo "LocalStack bootstrap complete."
