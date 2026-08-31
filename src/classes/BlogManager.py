"""
BlogManager - lightweight SQLite-backed storage for the self-authored Blog tab.
Lets the app owner publish their own posts (title, markdown content, optional
cover image) that persist across restarts, stored locally alongside the app.
"""
import os
import sqlite3
import datetime
import uuid


class BlogManager:
    def __init__(self, db_path: str = "KJScreener_blog.db", images_dir: str = None):
        self.db_path = db_path
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # .../src
        self.images_dir = images_dir or os.path.join(base_dir, "static", "blog_images")
        os.makedirs(self.images_dir, exist_ok=True)
        self._init_table()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_table(self):
        conn = self._get_conn()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS blog_posts (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    image_path TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            conn.commit()
        finally:
            conn.close()

    def add_post(self, title: str, content: str, image_bytes: bytes = None, image_ext: str = "png") -> str:
        post_id = uuid.uuid4().hex[:12]
        image_path = None
        if image_bytes:
            safe_ext = (image_ext or "png").lstrip(".").lower()
            if safe_ext not in ("png", "jpg", "jpeg", "gif", "webp"):
                safe_ext = "png"
            fname = f"{post_id}.{safe_ext}"
            fpath = os.path.join(self.images_dir, fname)
            with open(fpath, "wb") as f:
                f.write(image_bytes)
            image_path = fpath

        conn = self._get_conn()
        try:
            conn.execute(
                "INSERT INTO blog_posts (id, title, content, image_path, created_at) VALUES (?, ?, ?, ?, ?)",
                (post_id, title, content, image_path, datetime.datetime.now().isoformat()),
            )
            conn.commit()
        finally:
            conn.close()
        return post_id

    def list_posts(self):
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT id, title, content, image_path, created_at FROM blog_posts ORDER BY created_at DESC"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def delete_post(self, post_id: str):
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT image_path FROM blog_posts WHERE id = ?", (post_id,)).fetchone()
            if row and row["image_path"] and os.path.isfile(row["image_path"]):
                try:
                    os.remove(row["image_path"])
                except OSError:
                    pass
            conn.execute("DELETE FROM blog_posts WHERE id = ?", (post_id,))
            conn.commit()
        finally:
            conn.close()
