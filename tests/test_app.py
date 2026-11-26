import os
import gc
import tempfile
import unittest
from datetime import date

import app as app_module


class AppTests(unittest.TestCase):
    def setUp(self):
        fd, self.database = tempfile.mkstemp()
        os.close(fd)
        app_module.DATABASE = self.database
        app_module.app.config.update(TESTING=True, SECRET_KEY="test")
        app_module.init_db()
        self.client = app_module.app.test_client()

    def tearDown(self):
        gc.collect()
        with app_module.app.app_context():
            pass
        os.remove(self.database)

    def test_health_and_dashboard(self):
        health = self.client.get("/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.get_json()["status"], "healthy")
        self.assertEqual(self.client.get("/").status_code, 200)

    def test_dashboard_shows_current_month_and_six_month_chart(self):
        today = date.today()
        created_at = date(today.year, today.month, 10).isoformat() + " 12:00:00"
        with app_module.app.app_context():
            app_module.get_db().execute(
                """
                INSERT INTO students (name, email, course, created_at)
                VALUES (?, ?, ?, ?)
                """,
                ("Dashboard Student", "dashboard@example.com", "Python", created_at),
            )
            app_module.get_db().commit()

        response = self.client.get("/")
        html = response.get_data(as_text=True)
        self.assertIn("Enrollment activity", html)
        self.assertIn("Last 6 months", html)
        self.assertIn('data-count="1"', html)
        self.assertIn("New this month", html)
        self.assertIn("Dashboard Student", html)

    def test_add_edit_delete_student(self):
        response = self.client.post("/students/add", data={
            "name": "Ada Lovelace",
            "email": "ADA@example.com",
            "course": "Python",
        })
        self.assertEqual(response.status_code, 302)

        records = self.client.get("/api/students").get_json()
        student = records[0]
        self.assertEqual(student["email"], "ada@example.com")

        response = self.client.post(
            f"/students/{student['id']}/edit",
            data={"name": "Ada Byron", "email": "ada@example.com", "course": "Algorithms"},
        )
        self.assertEqual(response.status_code, 302)
        updated_student = self.client.get(
            f"/api/students/{student['id']}"
        ).get_json()
        self.assertEqual(updated_student["name"], "Ada Byron")
        self.assertEqual(updated_student["course"], "Algorithms")

        response = self.client.post(f"/students/{student['id']}/delete")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.get("/api/students").get_json(), [])

    def test_rejects_invalid_email(self):
        response = self.client.post("/students/add", data={
            "name": "Invalid",
            "email": "not-an-email",
            "course": "Python",
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.get("/api/students").get_json(), [])

    def test_missing_student_is_not_deleted(self):
        response = self.client.post("/students/999/delete")
        self.assertEqual(response.status_code, 404)

    def test_unknown_page_and_api_are_distinct(self):
        self.assertEqual(self.client.get("/unknown").status_code, 404)
        self.assertEqual(self.client.get("/api/unknown").status_code, 404)

    def test_rest_crud_api(self):
        create = self.client.post("/api/students", json={
            "name": "Grace Hopper",
            "email": "GRACE@example.com",
            "course": "COBOL",
        })
        self.assertEqual(create.status_code, 201)
        student_id = create.get_json()["id"]
        self.assertEqual(create.get_json()["email"], "grace@example.com")

        read = self.client.get(f"/api/students/{student_id}")
        self.assertEqual(read.status_code, 200)
        self.assertEqual(read.get_json()["name"], "Grace Hopper")

        patch = self.client.patch(
            f"/api/students/{student_id}",
            json={"course": "Computer Science"},
        )
        self.assertEqual(patch.status_code, 200)
        self.assertEqual(patch.get_json()["course"], "Computer Science")

        replace = self.client.put(
            f"/api/students/{student_id}",
            json={
                "name": "Grace Murray Hopper",
                "email": "grace@example.com",
                "course": "Compilers",
            },
        )
        self.assertEqual(replace.status_code, 200)
        self.assertEqual(replace.get_json()["name"], "Grace Murray Hopper")

        delete = self.client.delete(f"/api/students/{student_id}")
        self.assertEqual(delete.status_code, 204)
        self.assertEqual(
            self.client.get(f"/api/students/{student_id}").status_code,
            404,
        )

    def test_rest_api_validates_and_reports_duplicates(self):
        invalid = self.client.post("/api/students", json={
            "name": "Invalid",
            "email": "bad",
            "course": "Python",
        })
        self.assertEqual(invalid.status_code, 400)

        first = self.client.post("/api/students", json={
            "name": "One",
            "email": "same@example.com",
            "course": "Python",
        })
        self.assertEqual(first.status_code, 201)

        duplicate = self.client.post("/api/students", json={
            "name": "Two",
            "email": "same@example.com",
            "course": "Java",
        })
        self.assertEqual(duplicate.status_code, 409)


if __name__ == "__main__":
    unittest.main()
