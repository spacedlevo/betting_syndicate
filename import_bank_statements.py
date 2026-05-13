"""Import bank statements and link transactions to syndicate players."""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from app.database import SessionLocal, init_db
from app.bank_import import import_bank_statements

BANK_STATEMENTS_DIR = os.path.join(os.path.dirname(__file__), "bank statements")

if __name__ == "__main__":
    init_db()
    with SessionLocal() as session:
        import_bank_statements(BANK_STATEMENTS_DIR, session)
