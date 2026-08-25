import os
import tempfile

os.environ["DATABASE_PATH"] = os.path.join(tempfile.gettempdir(), "smoke_dashboard.db")

from app.db import get_session, init_db
from app import create_app
from app.models_db import User, Customer

init_db()

app = create_app()
app.testing = True
client = app.test_client()

with get_session() as s:
    emp = User(display_name="Smoke Employee", role="employee", is_active=True)
    s.add(emp)
    s.flush()
    cust1 = Customer(
        name="Acme Cylinder Co",
        address="123 Main St",
        city_state_zip="Detroit, MI 48201",
        phone="555-0100",
        email="acme@example.com",
    )
    cust2 = Customer(
        name="Beta Hydraulics",
        address="456 Oak Ave",
        city_state_zip="Chicago, IL 60601",
        phone="555-0200",
        email="beta@example.com",
    )
    s.add_all([cust1, cust2])
    s.commit()
    emp_id = emp.id

with client.session_transaction() as sess:
    sess["user_id"] = emp_id
    sess["role"] = "employee"

r = client.get("/portal/api/search?q=acme")
print("search status", r.status_code)
data = r.get_json()
print("results", data["results"])
assert any(
    item.get("type") == "customer" and item["name"] == "Acme Cylinder Co"
    for item in data["results"]
), "customer not in suggestions"

r2 = client.get("/employee/dashboard?q=beta")
print("dashboard status", r2.status_code)
text = r2.get_data(as_text=True)
assert "Matching Customers" in text, "matching customers heading missing"
assert "Beta Hydraulics" in text, "customer name missing from dashboard"
assert "View Quotes" in text, "view quotes link missing"

r3 = client.get("/employee/dashboard")
text3 = r3.get_data(as_text=True)
assert "Matching Customers" not in text3, "customer heading should not appear without query"

print("SMOKE OK")
