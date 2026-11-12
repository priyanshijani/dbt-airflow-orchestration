-- Kestrel Goods store database: the "production OLTP" source.
-- Every table carries updated_at so the ingestion layer can extract incrementally (FR-1.3).

CREATE TABLE customers (
    customer_id        BIGINT PRIMARY KEY,
    email              TEXT        NOT NULL,
    first_name         TEXT,
    last_name          TEXT,
    phone              TEXT,
    country_code       CHAR(2),
    region             TEXT,
    city               TEXT,
    accepts_marketing  BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at         TIMESTAMPTZ NOT NULL,
    updated_at         TIMESTAMPTZ NOT NULL
);

CREATE TABLE products (
    product_id   TEXT PRIMARY KEY,
    sku          TEXT          NOT NULL,
    name         TEXT          NOT NULL,
    category     TEXT,
    price_usd    NUMERIC(10,2) NOT NULL,
    cost_usd     NUMERIC(10,2) NOT NULL,
    is_active    BOOLEAN       NOT NULL DEFAULT TRUE,
    created_at   TIMESTAMPTZ   NOT NULL,
    updated_at   TIMESTAMPTZ   NOT NULL
);

CREATE TABLE orders (
    order_id        BIGINT PRIMARY KEY,
    order_number    TEXT          NOT NULL UNIQUE,
    customer_id     BIGINT        NOT NULL REFERENCES customers (customer_id),
    ga_session_id   BIGINT,
    ga_client_id    TEXT,
    status          TEXT          NOT NULL
        CHECK (status IN ('placed', 'paid', 'payment_failed', 'shipped', 'delivered', 'cancelled')),
    currency        CHAR(3)       NOT NULL DEFAULT 'USD',
    subtotal_usd    NUMERIC(10,2) NOT NULL,
    discount_usd    NUMERIC(10,2) NOT NULL DEFAULT 0,
    shipping_usd    NUMERIC(10,2) NOT NULL DEFAULT 0,
    tax_usd         NUMERIC(10,2) NOT NULL DEFAULT 0,
    total_usd       NUMERIC(10,2) NOT NULL,
    discount_code   TEXT,
    utm_source      TEXT,
    utm_medium      TEXT,
    utm_campaign    TEXT,
    device_type     TEXT,
    created_at      TIMESTAMPTZ   NOT NULL,
    updated_at      TIMESTAMPTZ   NOT NULL
);

CREATE TABLE order_items (
    order_item_id      BIGINT PRIMARY KEY,
    order_id           BIGINT        NOT NULL REFERENCES orders (order_id),
    product_id         TEXT          NOT NULL REFERENCES products (product_id),
    quantity           INTEGER       NOT NULL CHECK (quantity > 0),
    unit_price_usd     NUMERIC(10,2) NOT NULL,
    line_discount_usd  NUMERIC(10,2) NOT NULL DEFAULT 0,
    created_at         TIMESTAMPTZ   NOT NULL,
    updated_at         TIMESTAMPTZ   NOT NULL
);

CREATE TABLE refunds (
    refund_id   BIGINT PRIMARY KEY,
    order_id    BIGINT        NOT NULL REFERENCES orders (order_id),
    amount_usd  NUMERIC(10,2) NOT NULL,
    reason      TEXT,
    created_at  TIMESTAMPTZ   NOT NULL,
    updated_at  TIMESTAMPTZ   NOT NULL
);

CREATE INDEX ix_customers_updated_at   ON customers (updated_at);
CREATE INDEX ix_products_updated_at    ON products (updated_at);
CREATE INDEX ix_orders_updated_at      ON orders (updated_at);
CREATE INDEX ix_order_items_updated_at ON order_items (updated_at);
CREATE INDEX ix_refunds_updated_at     ON refunds (updated_at);
