SELECT 'CREATE DATABASE "cp_conversation"'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'cp_conversation')\gexec
