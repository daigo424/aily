SELECT 'CREATE DATABASE "checkpointer"'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'checkpointer')\gexec
