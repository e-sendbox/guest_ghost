"""Схема данных (шаг 0, обновлена в шаге 3): реляционные таблицы SQLite.

Шаг 4: + векторные таблицы sqlite-vec (hotel_card_emb, ghost_request_emb).
Модель упрощена: ghost_card объединён с ghost_request (одна заявка = одно приведение).
"""

import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS hotel_characteristic (
    id   INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS hotel_card (
    id              INTEGER PRIMARY KEY,
    name            TEXT NOT NULL,
    description     TEXT NOT NULL,
    characteristics TEXT NOT NULL DEFAULT '{}',
    restrictions    TEXT NOT NULL DEFAULT '[]',
    tags            TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS hotel_rooms (
    id        INTEGER PRIMARY KEY,
    hotel_id  INTEGER NOT NULL REFERENCES hotel_card(id),
    free_date TEXT,
    reserved  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS ghost_requirement (
    id   INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS ghost_request (
    id              INTEGER PRIMARY KEY,
    name            TEXT NOT NULL,
    anxiety         REAL NOT NULL,
    requirements    TEXT NOT NULL DEFAULT '{}',
    preferences     TEXT NOT NULL DEFAULT '',
    tags            TEXT NOT NULL DEFAULT '[]',
    deadline_date   TEXT NOT NULL,
    home_id         TEXT,
    match_percent   INTEGER,
    status          TEXT NOT NULL DEFAULT 'free',
    selection_hotel TEXT NOT NULL DEFAULT '[]',
    comment         TEXT,
    free_date       TEXT,
    chosen_date     TEXT,
    reserved_date   TEXT
);

CREATE VIRTUAL TABLE IF NOT EXISTS hotel_card_emb USING vec0(
    hotel_card_id INTEGER PRIMARY KEY,
    embedding FLOAT[768]
);

CREATE VIRTUAL TABLE IF NOT EXISTS ghost_request_emb USING vec0(
    ghost_request_id INTEGER PRIMARY KEY,
    embedding FLOAT[768]
);
"""


def create_schema(conn: sqlite3.Connection):
    conn.executescript(SCHEMA)
    conn.commit()

