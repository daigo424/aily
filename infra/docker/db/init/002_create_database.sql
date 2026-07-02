SELECT 'CREATE DATABASE "app"'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'app')\gexec

\connect app

CREATE EXTENSION IF NOT EXISTS vector;
