"""FastMail public reads and token-gated integration writes."""

import db

from .api_core import Resource, SQLiteBackend, create_sqlite_api

RESOURCES = (
    Resource("messages", "messages", "Messages", "Mailbox messages and conversation metadata.", search_fields=("from_name", "from_email", "to_email", "subject", "body")),
    Resource("contacts", "contacts", "Contacts", "Mail contacts and company details.", search_fields=("name", "email", "company")),
    Resource("labels", "labels", "Labels", "User-defined mailbox labels.", write_fields=("name", "color"), search_fields=("name",)),
    Resource("events", "events", "Calendar events", "Calendar events associated with the mailbox.", search_fields=("title", "location", "notes")),
)

backend = SQLiteBackend(db.DB_PATH, RESOURCES, initialize=db.init_schema)
api = create_sqlite_api(
    product="FastMail", version="1.0.0",
    description="Open integration access to FastMail messages, contacts, labels, and calendar events.",
    base_url="https://mail.fastsme.com", backend=backend, resources=RESOURCES,
)
