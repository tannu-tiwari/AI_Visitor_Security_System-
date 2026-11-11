import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

TEST_DIR = tempfile.mkdtemp(prefix="visitor_auth_tests_")
os.environ["VISITOR_DB_PATH"] = os.path.join(TEST_DIR, "auth_test.db")
os.environ["SECRET_KEY"] = "auth-test-secret-key"

from sqlalchemy import inspect, text  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402

import app as app_module  # noqa: E402
from core.database import db, ensure_user_schema  # noqa: E402
from core.models import User  # noqa: E402

app = app_module.app
app.config.update(TESTING=True)


def tearDownModule():
    with app.app_context():
        db.session.remove()
        db.engine.dispose()
    shutil.rmtree(TEST_DIR, ignore_errors=True)


class AuthTestCase(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        with app.app_context():
            db.drop_all()
            db.create_all()

    def create_user(self, username="guard1", password="correct horse battery staple",
                    full_name="Guard One", email=None, is_active=True,
                    role="admin", department=None):
        with app.app_context():
            user = User(
                username=username,
                full_name=full_name,
                email=email or None,
                role=role,
                department=department,
                is_active=is_active,
            )
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            return user.id

    def login_as(self, role, username=None, full_name=None):
        username = username or f"{role}_user"
        response = None
        self.create_user(
            username=username,
            full_name=full_name or f"{role.title()} User",
            role=role,
        )
        response = self.login(username=username)
        self.assertEqual(response.status_code, 302)
        return username

    def nav_html(self):
        body = self.client.get("/").get_data(as_text=True)
        return body.split('<nav class="sidebar-nav">', 1)[1].split("</nav>", 1)[0]

    def login(self, username="guard1", password="correct horse battery staple", next_url=""):
        data = {"username": username, "password": password}
        if next_url:
            data["next"] = next_url
        return self.client.post("/login", data=data)

    def test_user_table_schema(self):
        with app.app_context():
            inspector = inspect(db.engine)
            self.assertIn("users", inspector.get_table_names())

            columns = {
                column["name"]: column
                for column in inspector.get_columns("users")
            }
            self.assertEqual(
                set(columns),
                {
                    "id", "username", "password_hash", "full_name",
                    "email", "role", "department", "created_at", "is_active",
                },
            )
            for required in (
                "username", "password_hash", "full_name",
                "created_at", "is_active",
            ):
                self.assertFalse(columns[required]["nullable"], required)
            self.assertTrue(columns["email"]["nullable"])
            self.assertTrue(columns["role"]["nullable"])
            self.assertTrue(columns["department"]["nullable"])

    def test_user_password_is_hashed_and_defaults_apply(self):
        user_id = self.create_user(email="guard@example.com")

        with app.app_context():
            user = db.session.get(User, user_id)
            self.assertNotEqual(user.password_hash, "correct horse battery staple")
            self.assertNotIn("correct horse battery staple", user.password_hash)
            self.assertTrue(user.check_password("correct horse battery staple"))
            self.assertFalse(user.check_password("wrong password"))
            self.assertTrue(user.is_active)
            self.assertIsNotNone(user.created_at)
            self.assertEqual(user.email, "guard@example.com")

    def test_username_and_email_uniqueness(self):
        self.create_user(email="one@example.com")

        with app.app_context():
            duplicate_username = User(
                username="guard1", full_name="Other", email=None, role="security"
            )
            duplicate_username.set_password("another password")
            db.session.add(duplicate_username)
            with self.assertRaises(Exception):
                db.session.commit()
            db.session.rollback()

            duplicate_email = User(
                username="guard2", full_name="Other", email="one@example.com",
                role="security"
            )
            duplicate_email.set_password("another password")
            db.session.add(duplicate_email)
            with self.assertRaises(Exception):
                db.session.commit()
            db.session.rollback()

            blank_one = User(
                username="guard3", full_name="One", email=None, role="security"
            )
            blank_one.set_password("another password")
            blank_two = User(
                username="guard4", full_name="Two", email=None, role="host"
            )
            blank_two.set_password("another password")
            db.session.add_all([blank_one, blank_two])
            db.session.commit()
            self.assertEqual(db.session.query(User).count(), 3)

    def test_correct_credentials_log_in(self):
        self.create_user()

        response = self.login()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/")

        response = self.client.get("/auth-test")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["user"]["username"], "guard1")

    def test_wrong_password_and_unknown_user_share_generic_error(self):
        self.create_user()

        wrong_password = self.login(password="not the password")
        unknown_user = self.login(username="does-not-exist")

        for response in (wrong_password, unknown_user):
            self.assertEqual(response.status_code, 200)
            body = response.get_data(as_text=True)
            self.assertIn("Invalid username or password.", body)
            self.assertEqual(self.client.get("/auth-test").status_code, 302)

    def test_empty_credentials_are_rejected(self):
        response = self.client.post("/login", data={"username": "", "password": ""})
        self.assertEqual(response.status_code, 200)
        self.assertIn("Username and password are required.", response.get_data(as_text=True))

    def test_inactive_user_cannot_log_in(self):
        self.create_user(is_active=False)

        response = self.login()
        self.assertEqual(response.status_code, 200)
        self.assertIn("Invalid username or password.", response.get_data(as_text=True))
        self.assertEqual(self.client.get("/auth-test").status_code, 302)

    def test_logout_ends_session(self):
        self.create_user()
        self.login()
        self.assertEqual(self.client.get("/auth-test").status_code, 200)

        response = self.client.post("/logout")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])

        self.assertEqual(self.client.get("/auth-test").status_code, 302)

    def test_authenticated_login_page_redirects_to_dashboard(self):
        self.create_user()
        self.login()

        response = self.client.get("/login")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/")

    def test_protected_route_redirects_to_login_with_next(self):
        response = self.client.get("/auth-test")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login?next=%2Fauth-test", response.headers["Location"])

    def test_unsafe_next_urls_fall_back_to_dashboard(self):
        self.create_user()

        unsafe_targets = (
            "https://evil.example/steal",
            "http://evil.example",
            "//evil.example",
            "/\\evil.example",
            "/%2F%2Fevil.example",
            "/%5Cevil.example",
            "/%0d%0aLocation:%20https://evil.example",
            "javascript:alert(1)",
            "///evil.example",
        )

        for target in unsafe_targets:
            response = self.login(next_url=target)
            self.assertEqual(response.status_code, 302, target)
            self.assertEqual(response.headers["Location"], "/", target)
            self.client.post("/logout")

    def test_safe_next_url_is_respected(self):
        self.create_user()

        response = self.login(next_url="/approvals")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/approvals")
        self.assertEqual(self.client.get("/approvals").status_code, 200)

    def test_existing_visitor_workflow_still_works(self):
        host_id = self.create_user(
            username="workflow.host",
            full_name="Auth Host",
            role="host",
            department="Computer Science",
        )
        self.login_as("admin")
        self.assertEqual(self.client.get("/").status_code, 200)

        response = self.client.post("/register-visitor", json={
            "name": "Auth Workflow Visitor",
            "phone": "9990001234",
            "email": "",
            "purpose": "Meeting with Faculty",
            "host_id": host_id,
            "department": "Computer Science",
            "capture_filename": "",
        })
        self.assertEqual(response.status_code, 200)

        registrations = self.client.get("/api/registrations").get_json()
        visitor = next(
            record for record in registrations
            if record["Name"] == "Auth Workflow Visitor"
        )
        self.assertEqual(visitor["Approval Status"], "Pending")

        response = self.client.post(
            f"/host-approval/{visitor['Registration ID']}/approve",
            json={"decided_by": "Auth Host", "rejection_reason": ""},
        )
        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            self.client.post(
                "/mark-entry", json={"name": "Auth Workflow Visitor"}
            ).status_code,
            200,
        )
        open_visitors = self.client.get("/api/open-visitors").get_json()["visitors"]
        self.assertEqual(len(open_visitors), 1)
        self.assertEqual(open_visitors[0]["Visitor Name"], "Auth Workflow Visitor")

        self.assertEqual(
            self.client.post(
                "/mark-exit", json={"name": "Auth Workflow Visitor"}
            ).status_code,
            200,
        )
        self.assertEqual(self.client.get("/api/open-visitors").get_json()["visitors"], [])
        self.assertEqual(self.client.get("/api/visitor-logs").status_code, 200)
        self.assertEqual(self.client.get("/visitor-history").status_code, 200)
        self.assertEqual(self.client.get("/approval-history").status_code, 200)

    def test_role_values_are_controlled(self):
        with self.assertRaises(ValueError):
            User(username="bad-role", full_name="Bad Role", role="superuser")
        with self.assertRaises(ValueError):
            User(username="missing-role", full_name="Missing Role")

        user = User(username="valid-role", full_name="Valid Role", role="ADMIN")
        self.assertEqual(user.role, "admin")
        self.assertEqual(user.role_label, "Administrator")

        user.role = "HOST"
        self.assertEqual(user.role, "host")
        self.assertEqual(user.role_label, "Host")

        with self.assertRaises(ValueError):
            user.role = "root"

    def test_schema_update_preserves_existing_accounts(self):
        existing_hash = generate_password_hash("legacy password")

        with app.app_context():
            db.session.remove()
            with db.engine.begin() as connection:
                connection.execute(text("DROP TABLE users"))
                connection.execute(text("""
                    CREATE TABLE users (
                        id INTEGER NOT NULL,
                        username VARCHAR(80) NOT NULL,
                        password_hash VARCHAR(255) NOT NULL,
                        full_name VARCHAR(120) NOT NULL,
                        email VARCHAR(200),
                        created_at DATETIME NOT NULL,
                        is_active BOOLEAN NOT NULL,
                        PRIMARY KEY (id),
                        UNIQUE (username),
                        UNIQUE (email)
                    )
                """))
                connection.execute(
                    text("""
                        INSERT INTO users (
                            username, password_hash, full_name, email,
                            created_at, is_active
                        ) VALUES (
                            'legacy-admin', :password_hash, 'Legacy Admin',
                            NULL, '2026-01-01 10:00:00', 1
                        )
                    """),
                    {"password_hash": existing_hash},
                )

            added = ensure_user_schema()
            self.assertEqual(set(added), {"role", "department"})
            self.assertEqual(ensure_user_schema(), [])

            columns = {
                column["name"]
                for column in inspect(db.engine).get_columns("users")
            }
            self.assertIn("role", columns)
            self.assertIn("department", columns)

            with db.engine.begin() as connection:
                row = connection.execute(
                    text("""
                        SELECT password_hash, role, department
                        FROM users WHERE username = 'legacy-admin'
                    """)
                ).mappings().one()
            self.assertEqual(row["password_hash"], existing_hash)
            self.assertIsNone(row["role"])
            self.assertIsNone(row["department"])

            with self.assertRaises(Exception):
                with db.engine.begin() as connection:
                    connection.execute(
                        text("UPDATE users SET role = 'superuser'")
                    )

            user = db.session.execute(
                db.select(User).where(User.username == "legacy-admin")
            ).scalar_one()
            user.role = "admin"
            db.session.commit()
            self.assertTrue(user.check_password("legacy password"))
            self.assertEqual(user.role_label, "Administrator")

    def test_rbac_page_permissions(self):
        cases = {
            "admin": {
                "allowed": (
                    "/", "/registration", "/recognition", "/approvals",
                    "/approval-history", "/inside-visitors", "/visitor-history",
                ),
                "denied": (),
            },
            "security": {
                "allowed": (
                    "/", "/registration", "/recognition",
                    "/inside-visitors", "/visitor-history",
                ),
                "denied": ("/approvals", "/approval-history"),
            },
            "host": {
                "allowed": ("/", "/approvals", "/approval-history"),
                "denied": (
                    "/registration", "/recognition",
                    "/inside-visitors", "/visitor-history",
                ),
            },
        }

        first = True
        for role, expectations in cases.items():
            if not first:
                self.client.post("/logout")
            first = False

            with self.subTest(role=role):
                self.login_as(role)
                for path in expectations["allowed"]:
                    self.assertEqual(self.client.get(path).status_code, 200, path)
                for path in expectations["denied"]:
                    response = self.client.get(path)
                    self.assertEqual(response.status_code, 403, path)
                    self.assertIn("text/html", response.content_type)

    def test_rbac_api_permissions(self):
        for path in (
            "/api/registrations",
            "/api/pending-approvals",
            "/api/approval-history",
        ):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 401, path)
            self.assertIn("application/json", response.content_type)
            self.assertIn("Authentication required", response.get_json()["error"])

        response = self.client.post("/mark-entry", json={"name": "Nobody"})
        self.assertEqual(response.status_code, 401)
        self.assertIn("application/json", response.content_type)

        self.login_as("admin")
        for path in (
            "/api/registrations",
            "/api/pending-approvals",
            "/api/approval-history",
            "/api/visitor-logs",
            "/api/open-visitors",
        ):
            self.assertEqual(self.client.get(path).status_code, 200, path)
        self.client.post("/logout")

        self.login_as("security")
        for path in ("/api/registrations", "/api/visitor-logs", "/api/open-visitors"):
            self.assertEqual(self.client.get(path).status_code, 200, path)
        for path in ("/api/pending-approvals", "/api/approval-history"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 403, path)
            self.assertIn("application/json", response.content_type)
            self.assertIn("permission", response.get_json()["error"].lower())
        self.assertEqual(
            self.client.post(
                "/host-approval/UNKNOWN/approve", json={"decided_by": "Security"}
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post("/mark-entry", json={}).status_code,
            400,
        )
        self.client.post("/logout")

        self.login_as("host")
        for path in (
            "/api/pending-approvals",
            "/api/approval-history",
        ):
            self.assertEqual(self.client.get(path).status_code, 200, path)
        for path in (
            "/api/registrations",
            "/visitor-history",
            "/api/visitor-logs",
            "/api/open-visitors",
        ):
            self.assertEqual(self.client.get(path).status_code, 403, path)
        self.assertEqual(
            self.client.post("/register-visitor", json={"name": "Nope"}).status_code,
            403,
        )
        self.assertEqual(
            self.client.post("/mark-entry", json={"name": "Nope"}).status_code,
            403,
        )

    def test_host_can_approve_but_cannot_register_or_mark_entry(self):
        host_id = self.create_user(
            username="approval.host",
            full_name="Host User",
            role="host",
            department="Computer Science",
        )
        self.login_as("admin")
        response = self.client.post("/register-visitor", json={
            "name": "Host Approval Visitor",
            "phone": "9990001234",
            "email": "",
            "purpose": "Meeting with Faculty",
            "host_id": host_id,
            "department": "Computer Science",
            "capture_filename": "",
        })
        self.assertEqual(response.status_code, 200)
        visitor = next(
            record for record in self.client.get("/api/registrations").get_json()
            if record["Name"] == "Host Approval Visitor"
        )
        self.client.post("/logout")

        self.login_as("host")
        self.assertEqual(
            self.client.post(
                f"/host-approval/{visitor['Registration ID']}/approve",
                json={"decided_by": "Host User", "rejection_reason": ""},
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.post(
                "/register-visitor", json={"name": "Blocked Visitor"}
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                "/mark-entry", json={"name": "Host Approval Visitor"}
            ).status_code,
            403,
        )
        self.assertEqual(self.client.get("/api/registrations").status_code, 403)

    def test_host_directory_endpoints_are_dynamic(self):
        cs_one = self.create_user(
            username="host.cs.one",
            full_name="Alice CS",
            role="host",
            department="Computer Science",
        )
        cs_two = self.create_user(
            username="host.cs.two",
            full_name="Bob CS",
            role="host",
            department="Computer Science",
        )
        self.create_user(
            username="host.it",
            full_name="Carol IT",
            role="host",
            department="Information Technology",
        )
        self.create_user(
            username="host.inactive",
            full_name="Inactive Host",
            role="host",
            department="Mechanical Engineering",
            is_active=False,
        )
        self.create_user(
            username="security.user",
            full_name="Security User",
            role="security",
            department="Civil Engineering",
        )
        self.create_user(
            username="host.empty",
            full_name="Empty Department",
            role="host",
            department="   ",
        )

        self.login_as("security")

        response = self.client.get("/api/departments")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json()["departments"],
            ["Computer Science", "Information Technology"],
        )

        response = self.client.get(
            "/api/hosts",
            query_string={"department": "Computer Science"},
        )
        self.assertEqual(response.status_code, 200)
        hosts = response.get_json()["hosts"]
        self.assertEqual(
            [(host["id"], host["full_name"]) for host in hosts],
            [(cs_one, "Alice CS"), (cs_two, "Bob CS")],
        )

        for department in ("Mechanical Engineering", "Civil Engineering"):
            response = self.client.get(
                "/api/hosts",
                query_string={"department": department},
            )
            self.assertEqual(response.get_json()["hosts"], [])

        response = self.client.get("/api/hosts")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["hosts"], [])

        self.client.post("/logout")
        self.assertEqual(self.client.get("/api/departments").status_code, 401)
        self.login_as("host")
        self.assertEqual(self.client.get("/api/departments").status_code, 403)

    def test_registration_page_uses_dynamic_host_selects(self):
        self.login_as("security")
        body = self.client.get("/registration").get_data(as_text=True)

        self.assertIn('name="department"', body)
        self.assertIn('name="host_id"', body)
        self.assertIn("Select Department First", body)
        self.assertNotIn('<option>Computer Science</option>', body)
        self.assertNotIn('placeholder="Faculty or staff name"', body)

    def test_registration_validates_selected_host(self):
        host_id = self.create_user(
            username="dr.rao",
            full_name="Dr. Rao",
            role="host",
            department="Computer Science",
        )
        inactive_host_id = self.create_user(
            username="inactive.host",
            full_name="Inactive Host",
            role="host",
            department="Computer Science",
            is_active=False,
        )
        non_host_id = self.create_user(
            username="not.a.host",
            full_name="Not A Host",
            role="security",
            department="Computer Science",
        )

        self.login_as("security")

        def submit(**overrides):
            payload = {
                "name": "Dynamic Host Visitor",
                "phone": "9990001234",
                "email": "",
                "purpose": "Meeting with Faculty",
                "host_id": host_id,
                "department": "Computer Science",
                "capture_filename": "",
            }
            payload.update(overrides)
            return self.client.post("/register-visitor", json=payload)

        invalid_payloads = (
            {"host_id": ""},
            {"host_id": None},
            {"host_id": "not-an-id"},
            {"host_id": 999999},
            {"host_id": non_host_id},
            {"host_id": inactive_host_id},
            {"department": "Information Technology"},
        )

        for overrides in invalid_payloads:
            response = submit(**overrides)
            self.assertEqual(response.status_code, 400, overrides)
            self.assertFalse(response.get_json()["success"])

        self.assertEqual(self.client.get("/api/registrations").get_json(), [])

        response = submit()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["success"])

        visitor = next(
            record for record in self.client.get("/api/registrations").get_json()
            if record["Name"] == "Dynamic Host Visitor"
        )
        self.assertEqual(visitor["Host"], "Dr. Rao")
        self.assertEqual(visitor["Department"], "Computer Science")
        self.assertEqual(visitor["Approval Status"], "Pending")

    def test_inactive_user_loses_session_access(self):
        user_id = self.create_user(role="admin")
        self.login()

        with app.app_context():
            user = db.session.get(User, user_id)
            user.is_active = False
            db.session.commit()

        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])

        response = self.client.get("/api/registrations")
        self.assertEqual(response.status_code, 401)

    def test_unassigned_role_is_denied(self):
        user_id = self.create_user(role="admin")
        with app.app_context():
            user = db.session.get(User, user_id)
            user.role = None
            db.session.commit()

        self.login()
        response = self.client.get("/")
        self.assertEqual(response.status_code, 403)
        self.assertIn("text/html", response.content_type)

        response = self.client.get("/api/registrations")
        self.assertEqual(response.status_code, 403)
        self.assertIn("application/json", response.content_type)

    def test_role_based_navigation_and_account_display(self):
        self.login_as("admin", full_name="Ada Admin")
        nav = self.nav_html()
        for label in (
            "Dashboard", "Visitor Registration", "Face Recognition",
            "Approvals", "Inside Visitors", "Visitor History", "User Management",
        ):
            self.assertIn(label, nav)
        self.assertNotIn("My Approval Requests", nav)
        self.assertNotIn("Approval History", nav)
        body = self.client.get("/").get_data(as_text=True)
        self.assertIn("Ada Admin", body)
        self.assertIn("Administrator", body)
        self.assertIn("Log out", body)
        self.assertIn("Recent Visitor Activity", body)
        self.assertIn("Pending Host Approvals", body)
        self.assertIn("Currently Inside", body)
        self.client.post("/logout")

        self.login_as("security", full_name="Sam Security")
        nav = self.nav_html()
        for label in (
            "Dashboard", "Visitor Registration", "Face Recognition",
            "Inside Visitors", "Visitor History",
        ):
            self.assertIn(label, nav)
        for label in (
            "Approvals", "Approval History", "User Management",
            "My Approval Requests",
        ):
            self.assertNotIn(label, nav)
        body = self.client.get("/").get_data(as_text=True)
        self.assertIn("Sam Security", body)
        self.assertIn("Security Guard", body)
        self.assertIn("Recent Visitor Activity", body)
        self.assertIn("Currently Inside", body)
        self.assertNotIn("Pending Host Approvals", body)
        self.client.post("/logout")

        self.login_as("host", full_name="Holly Host")
        nav = self.nav_html()
        for label in ("Dashboard", "My Approval Requests", "Approval History"):
            self.assertIn(label, nav)
        for label in (
            "Visitor Registration", "Face Recognition", "Inside Visitors",
            "Visitor History", "User Management",
        ):
            self.assertNotIn(label, nav)
        body = self.client.get("/").get_data(as_text=True)
        self.assertIn("Holly Host", body)
        self.assertIn("Host", body)
        self.assertIn("Pending Host Approvals", body)
        self.assertNotIn("Recent Visitor Activity", body)
        self.assertNotIn("Currently Inside", body)

    def test_health_and_login_remain_public(self):
        self.assertEqual(self.client.get("/health").status_code, 200)
        self.assertEqual(self.client.get("/login").status_code, 200)

    def test_create_user_cli_hashes_password(self):
        runner = app.test_cli_runner()
        result = runner.invoke(
            args=[
                "create-user",
                "--username", "cli-user",
                "--full-name", "CLI User",
                "--email", "cli@example.com",
                "--role", "security",
                "--department", "Security Office",
            ],
            input="cli password\ncli password\n",
        )
        self.assertEqual(result.exit_code, 0, result.output)

        with app.app_context():
            user = db.session.execute(
                db.select(User).where(User.username == "cli-user")
            ).scalar_one()
            self.assertEqual(user.full_name, "CLI User")
            self.assertEqual(user.role, "security")
            self.assertEqual(user.department, "Security Office")
            self.assertTrue(user.check_password("cli password"))
            self.assertNotEqual(user.password_hash, "cli password")

    def test_assign_role_cli_updates_existing_account(self):
        self.create_user(role="security")

        runner = app.test_cli_runner()
        result = runner.invoke(
            args=[
                "assign-role",
                "--username", "guard1",
                "--role", "admin",
                "--department", "Administration",
            ],
        )
        self.assertEqual(result.exit_code, 0, result.output)

        with app.app_context():
            user = db.session.execute(
                db.select(User).where(User.username == "guard1")
            ).scalar_one()
            self.assertEqual(user.role, "admin")
            self.assertEqual(user.role_label, "Administrator")
            self.assertEqual(user.department, "Administration")
            self.assertTrue(user.check_password("correct horse battery staple"))


if __name__ == "__main__":
    unittest.main()
