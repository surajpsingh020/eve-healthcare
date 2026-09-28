-- Creates the test database if it doesn't exist.
-- This runs once on first postgres container startup.
SELECT 'CREATE DATABASE eve_healthcare_test'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'eve_healthcare_test')\gexec
