import json
import random
from pathlib import Path

# This script generates synthetic log data for testing purposes. It creates 10,000 log entries with varying messages, services, and severity levels, and saves them to a JSON file.

# Resolve project root (2 levels up from script)

BASE_DIR = Path(__file__).resolve().parent.parent

# Target directory

log_dir = BASE_DIR / "data"

# File path

log_file = log_dir / "logs.json"

services = [
    "customer_etl", "payment_service", "account_etl",
    "file_ingestion", "auth_service", "order_service",
    "notification_service", "inventory_service", "reporting_engine"
]

severities = ["ERROR", "CRITICAL", "WARNING"]

# Define error message templates with placeholders for dynamic content

error_templates = [
    "ORA-06502 numeric or value error in procedure {proc}",
    "ORA-00001 unique constraint violated in table {table}",
    "Connection timeout while calling {api}",
    "Failed to connect to database {db}",
    "Null pointer exception in module {module}",
    "File not found while processing {file}",
    "Permission denied for resource {resource}",
    "Invalid input format for field {field}",
    "Data inconsistency detected in {table}",
    "API returned 500 error for endpoint {api}",
    "Authentication failed for user {user}",
    "Index out of bounds in array processing",
    "Memory overflow in batch job {job}",
    "Deadlock detected in transaction processing",
    "Disk space exhausted on server {server}",
    "Service unavailable: {service_dep}",
    "JSON parsing error in request payload",
    "SSL handshake failed with external service",
    "Timeout while reading from message queue",
    "Duplicate record found for key {key}"
]

# Define placeholders and their possible values for dynamic content in log messages
placeholders = {
    "proc": ["LOAD_CUSTOMER", "UPDATE_ACCOUNT", "SYNC_ORDER"],
    "table": ["CUSTOMER", "ORDERS", "PAYMENTS"],
    "api": ["payment API", "order API", "auth API"],
    "db": ["ORACLE_DB", "POSTGRES_DB"],
    "module": ["billing", "checkout", "reconciliation"],
    "file": ["transactions.csv", "customers.json"],
    "resource": ["S3 bucket", "config file"],
    "field": ["amount", "date", "customer_id"],
    "user": ["user123", "admin", "guest"],
    "job": ["daily_batch", "monthly_recon"],
    "server": ["server-1", "server-2"],
    "service_dep": ["inventory_service", "payment_gateway"],
    "key": ["ACC123", "ORD456"]
}

# Function to fill in the placeholders in the error templates with random values
def fill_template(template):
    for key in placeholders:
        if f"{{{key}}}" in template:
            template = template.replace(
                f"{{{key}}}", random.choice(placeholders[key])
            )
    return template

logs = []

# Generate 10,000 log entries with random messages, services, and severity levels
for i in range(1, 10001):
    template = random.choice(error_templates)
    message = fill_template(template)

    log = {
        "log_id": str(i),
        "message": message,
        "service": random.choice(services),
        "severity": random.choice(severities)
    }
    logs.append(log)

# Save to file
with open(log_file, "w") as f:
    json.dump(logs, f, indent=2)

print("Generated 10,000 log entries!")