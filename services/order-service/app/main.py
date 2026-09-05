import os
from decimal import Decimal
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import urlopen
import json

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import pymysql


def get_connection() -> pymysql.connections.Connection:
    return pymysql.connect(
        host=os.getenv("MYSQL_HOST", "mysql"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "hardtech"),
        password=os.getenv("MYSQL_PASSWORD", "hardtech"),
        database=os.getenv("MYSQL_DATABASE", "hardtech_orders"),
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )


app = FastAPI(title="Order Service", version="1.0.0")


def get_catalog_service_url() -> str:
    return os.getenv("CATALOG_SERVICE_URL", "http://catalog-service:8002")


def fetch_product_snapshot(product_id: int) -> dict[str, Any]:
    product_url = f"{get_catalog_service_url()}/api/products/{product_id}"
    try:
        with urlopen(product_url, timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code == 404:
            raise HTTPException(status_code=400, detail=f"Product {product_id} not found") from exc
        raise HTTPException(status_code=502, detail="Catalog Service error") from exc
    except URLError as exc:
        raise HTTPException(status_code=503, detail="Catalog Service unavailable") from exc


class OrderItemRequest(BaseModel):
    product_id: int
    quantity: int


class CreateOrderRequest(BaseModel):
    user_id: str
    items: list[OrderItemRequest]


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"service": "order-service", "status": "healthy", "version": "1.0.0"}


@app.post("/api/orders")
def create_order(payload: CreateOrderRequest) -> dict[str, Any]:
    if not payload.items:
        raise HTTPException(status_code=400, detail="Order items are required")

    order_snapshots = []
    subtotal = Decimal("0.00")
    for item in payload.items:
        product = fetch_product_snapshot(item.product_id)
        unit_price = Decimal(str(product["price"]))
        item_subtotal = unit_price * item.quantity
        order_snapshots.append(
            {
                "product_id": item.product_id,
                "product_sku": product["sku"],
                "product_name": product["name"],
                "quantity": item.quantity,
                "unit_price": unit_price,
                "subtotal": item_subtotal,
            }
        )
        subtotal += item_subtotal

    tax = (subtotal * Decimal("0.18")).quantize(Decimal("0.01"))
    shipping_cost = Decimal("25.00")
    total_amount = subtotal + tax + shipping_cost

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO orders (user_id, status, subtotal, tax, shipping_cost, total_amount)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (payload.user_id, "PENDING", str(subtotal), str(tax), str(shipping_cost), str(total_amount)),
            )
            order_id = cursor.lastrowid

            for item in order_snapshots:
                cursor.execute(
                    """
                    INSERT INTO order_items
                    (order_id, product_id, product_sku, product_name, quantity, unit_price, subtotal)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        order_id,
                        item["product_id"],
                        item["product_sku"],
                        item["product_name"],
                        item["quantity"],
                        str(item["unit_price"]),
                        str(item["subtotal"]),
                    ),
                )

        conn.commit()
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail="MySQL error") from exc
    finally:
        conn.close()

    return {"order_id": order_id, "status": "PENDING", "total_amount": str(total_amount)}


@app.get("/api/orders/user/{user_id}")
def get_orders_by_user(user_id: str) -> Any:
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM orders WHERE user_id = %s ORDER BY created_at DESC",
                (user_id,),
            )
            orders = cursor.fetchall()
    finally:
        conn.close()
    return list(orders)


VALID_STATUSES = {"PENDING", "PAID", "SHIPPED", "CANCELLED"}


class UpdateStatusRequest(BaseModel):
    status: str


@app.patch("/api/orders/{order_id}/status")
def update_order_status(order_id: int, payload: UpdateStatusRequest) -> dict[str, Any]:
    if payload.status not in VALID_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {', '.join(sorted(VALID_STATUSES))}",
        )
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, status FROM orders WHERE id = %s", (order_id,))
            order = cursor.fetchone()
            if not order:
                raise HTTPException(status_code=404, detail="Order not found")
            cursor.execute(
                "UPDATE orders SET status = %s WHERE id = %s",
                (payload.status, order_id),
            )
        conn.commit()
    except HTTPException:
        raise
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail="MySQL error") from exc
    finally:
        conn.close()
    return {"order_id": order_id, "status": payload.status}


@app.get("/api/orders/{order_id}")
def get_order(order_id: int) -> dict[str, Any]:
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM orders WHERE id = %s", (order_id,))
            order = cursor.fetchone()
            if not order:
                raise HTTPException(status_code=404, detail="Order not found")

            cursor.execute("SELECT * FROM order_items WHERE order_id = %s ORDER BY id ASC", (order_id,))
            items = cursor.fetchall()
    finally:
        conn.close()

    return {"order": order, "items": items}
