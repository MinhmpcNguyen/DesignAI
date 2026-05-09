-- Create role and database for TKNT project.
-- Run as a PostgreSQL superuser (e.g., postgres).

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'Architecture') THEN
        CREATE ROLE "Architecture" LOGIN PASSWORD 'password';
    END IF;
END $$;

SELECT format('CREATE DATABASE %I OWNER %I', 'Design', 'Architecture')
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'Design')
\gexec

SELECT format('GRANT ALL PRIVILEGES ON DATABASE %I TO %I', 'Design', 'Architecture')
WHERE EXISTS (SELECT 1 FROM pg_database WHERE datname = 'Design')
\gexec
