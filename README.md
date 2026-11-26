# MEVI Management Portal

A Flask and SQLite student management application.

## Features

- Dashboard with student and course totals
- Monthly enrollment chart and new-this-month metric
- Recent student overview
- Add, edit, and delete students
- Email validation and duplicate-email protection
- JSON student API
- Health check endpoint
- Responsive built-in interface

## CRUD API

| Operation | Method | Endpoint |
|---|---|---|
| List students | `GET` | `/api/students` |
| Create student | `POST` | `/api/students` |
| Get one student | `GET` | `/api/students/<id>` |
| Replace student | `PUT` | `/api/students/<id>` |
| Update student fields | `PATCH` | `/api/students/<id>` |
| Delete student | `DELETE` | `/api/students/<id>` |

Example create request:

```json
{
  "name": "Ada Lovelace",
  "email": "ada@example.com",
  "course": "Python"
}
```

## Run

```powershell
python -m pip install -r requirements.txt
python app.py
```

Open `http://localhost:5001`.

## Run with Docker

Build the image:

```powershell
docker build -t mevi-management:latest .
```

Run the app with a persistent SQLite database:

```powershell
docker volume create mevi-data
docker run -d --name mevi-management -p 5001:5001 -v mevi-data:/app/instance mevi-management:latest
```

Open `http://localhost:5001`. To stop and remove the container, run `docker rm -f mevi-management`. The `mevi-data` volume is retained so student records remain available if you recreate the container.

## Test

```powershell
python -m unittest discover -s tests -v
```

The SQLite database is stored at `instance/management.db`. Set `DATABASE_PATH` to use another database file.
