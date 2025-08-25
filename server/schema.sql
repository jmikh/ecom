-- PostgreSQL Schema for E-commerce Products Database

CREATE TABLE IF NOT EXISTS products (
    url TEXT,
    size TEXT,
    price DECIMAL(10, 2),
    original_price DECIMAL(10, 2),
    review_avg_score DECIMAL(10, 2),
    images TEXT[],
    options TEXT[],
    reviews TEXT[],
    material TEXT,
    product_name TEXT,
    material_and_care TEXT,
    about_this_mantra TEXT,
    shipping_and_returns TEXT,
    product_details_fit TEXT,
    category TEXT
);