"""
app/routers/__init__.py
=======================

WHY THIS FOLDER EXISTS:
  FastAPI routers group related endpoints together (like blueprints in Flask).
  Each file in this folder handles one "resource" or feature area.

  Planned routers (Phases 3-7):
    - auth.py          → POST /auth/signup, /auth/login, GET /auth/me
    - listings.py      → CRUD for food listings + claim/complete actions
    - notifications.py → GET /notifications, mark as read
    - admin.py         → GET /admin/stats, /admin/dashboard
    - pages.py         → Jinja2 HTML page routes (landing, signup UI, etc.)

  HOW ROUTERS WORK:
    Each router is created with APIRouter() and then registered in main.py
    with app.include_router(). This keeps main.py clean — it only stitches
    things together, not define routes directly.
"""
