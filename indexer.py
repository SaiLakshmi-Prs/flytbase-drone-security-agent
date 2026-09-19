"""Cross-Domain Persistent Frame Indexing Engine using SQLite with FTS5.

Provides relational and full-text search storage for frame-by-frame drone observations,
enabling temporal queries, geospatial lookups, and multi-attribute entity searches
(e.g., 'show all truck events', 'find events between 00:00 and 01:00').
"""

from __future__ import annotations

import datetime
import json
import logging
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional, Tuple, Union

from perception import DetectedEntity, PerceptionResult
from simulator import VideoFrame

logger = logging.getLogger(__name__)


class FrameIndexer:
    """Persistent SQLite database manager indexing drone frames, entities, and security alerts."""

    def __init__(self, db_path: Union[str, Path] = "drone_security.db") -> None:
        """Initialize SQLite database connection and establish tables.

        Args:
            db_path: Path to the SQLite database file or ':memory:' for in-memory testing.
        """
        self.db_path = str(db_path)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_pragmas()
        self._create_tables()

    def _init_pragmas(self) -> None:
        """Configure high-concurrency SQLite PRAGMAs (WAL mode, foreign keys)."""
        cursor = self.conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")
        if self.db_path != ":memory:":
            cursor.execute("PRAGMA journal_mode = WAL;")
            cursor.execute("PRAGMA synchronous = NORMAL;")
        self.conn.commit()

    def _create_tables(self) -> None:
        """Create relational schema and FTS5 virtual table for full-text indexing."""
        cursor = self.conn.cursor()

        # Frames Table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS frames (
                frame_id INTEGER PRIMARY KEY,
                timestamp TEXT NOT NULL,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                altitude_m REAL NOT NULL,
                battery_percent REAL NOT NULL,
                dock_status TEXT NOT NULL,
                location_name TEXT NOT NULL,
                raw_description TEXT NOT NULL,
                primary_log_message TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )

        # Entities Table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS entities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                frame_id INTEGER NOT NULL,
                entity_id TEXT NOT NULL,
                category TEXT NOT NULL,
                label TEXT NOT NULL,
                confidence REAL NOT NULL,
                threat_indicator TEXT NOT NULL,
                threat_rationale TEXT,
                attributes_json TEXT,
                FOREIGN KEY (frame_id) REFERENCES frames(frame_id) ON DELETE CASCADE
            );
            """
        )

        # Alerts Table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS alerts (
                alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
                frame_id INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                severity TEXT NOT NULL,
                rule_name TEXT NOT NULL,
                message TEXT NOT NULL,
                location_name TEXT NOT NULL,
                details_json TEXT,
                FOREIGN KEY (frame_id) REFERENCES frames(frame_id) ON DELETE CASCADE
            );
            """
        )

        # Indexes for fast lookup
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_frames_time ON frames(timestamp);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_frames_location ON frames(location_name);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_entities_frame ON entities(frame_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_entities_category ON entities(category);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_entities_label ON entities(label);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_time ON alerts(timestamp);")

        # Full Text Search (FTS5) for cross-domain natural search
        try:
            cursor.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS frames_fts USING fts5(
                    frame_id UNINDEXED,
                    location_name,
                    primary_log_message,
                    raw_description
                );
                """
            )
        except sqlite3.OperationalError as e:
            logger.warning("FTS5 table initialization skipped: %s", e)

        self.conn.commit()

    def index_frame(self, frame: VideoFrame, perception: PerceptionResult) -> None:
        """Persistently index a synchronized frame and all extracted entities.

        Args:
            frame: Synchronized VideoFrame object.
            perception: Structured PerceptionResult containing extracted entities.
        """
        cursor = self.conn.cursor()
        iso_time = frame.timestamp.isoformat()
        now_str = datetime.datetime.utcnow().isoformat()

        # Insert or replace frame
        cursor.execute(
            """
            INSERT OR REPLACE INTO frames (
                frame_id, timestamp, latitude, longitude, altitude_m,
                battery_percent, dock_status, location_name,
                raw_description, primary_log_message, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                frame.frame_id,
                iso_time,
                frame.telemetry.latitude,
                frame.telemetry.longitude,
                frame.telemetry.altitude_m,
                frame.telemetry.battery_percent,
                frame.telemetry.dock_status,
                frame.telemetry.location_name,
                frame.raw_description,
                perception.primary_log_message,
                now_str,
            ),
        )

        # Index in FTS5
        try:
            cursor.execute(
                """
                INSERT INTO frames_fts (frame_id, location_name, primary_log_message, raw_description)
                VALUES (?, ?, ?, ?);
                """,
                (
                    frame.frame_id,
                    frame.telemetry.location_name,
                    perception.primary_log_message,
                    frame.raw_description,
                ),
            )
        except sqlite3.OperationalError:
            pass

        # Insert entities
        for entity in perception.entities:
            cursor.execute(
                """
                INSERT INTO entities (
                    frame_id, entity_id, category, label, confidence,
                    threat_indicator, threat_rationale, attributes_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    frame.frame_id,
                    entity.entity_id,
                    entity.category,
                    entity.label,
                    entity.confidence,
                    entity.threat_indicator,
                    entity.threat_rationale,
                    json.dumps(entity.attributes),
                ),
            )

        self.conn.commit()

    def record_alert(
        self,
        frame_id: int,
        timestamp: datetime.datetime,
        severity: str,
        rule_name: str,
        message: str,
        location_name: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Store a security or safety alert triggered by the agent.

        Returns:
            The generated alert_id.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO alerts (
                frame_id, timestamp, severity, rule_name, message, location_name, details_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            (
                frame_id,
                timestamp.isoformat(),
                severity,
                rule_name,
                message,
                location_name,
                json.dumps(details or {}),
            ),
        )
        self.conn.commit()
        return int(cursor.lastrowid)

    # -------------------------------------------------------------------------
    # Query APIs for Cross-Domain Search & NL Follow-up
    # -------------------------------------------------------------------------

    def query_by_object(self, object_term: str) -> List[Dict[str, Any]]:
        """Query indexed frames matching a target object name or category.

        Example: object_term='truck' matches 'Blue Ford F150', 'truck', etc.
        """
        cursor = self.conn.cursor()
        pattern = f"%{object_term.strip()}%"
        cursor.execute(
            """
            SELECT f.frame_id, f.timestamp, f.location_name, f.primary_log_message,
                   e.label, e.category, e.attributes_json, e.threat_indicator
            FROM frames f
            JOIN entities e ON f.frame_id = e.frame_id
            WHERE e.label LIKE ? OR e.category LIKE ? OR e.attributes_json LIKE ? OR f.raw_description LIKE ?
            ORDER BY f.timestamp ASC;
            """,
            (pattern, pattern, pattern, pattern),
        )
        rows = cursor.fetchall()
        return [dict(r) for r in rows]

    def query_truck_events(self) -> List[Dict[str, Any]]:
        """Query all truck and vehicle events specifically.

        Fulfills sample requirement: 'show all truck events'.
        """
        return self.query_by_object("truck")

    def query_by_time_range(
        self, start_dt: datetime.datetime, end_dt: datetime.datetime
    ) -> List[Dict[str, Any]]:
        """Query indexed frames within a timestamp window."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT frame_id, timestamp, location_name, battery_percent, primary_log_message, raw_description
            FROM frames
            WHERE timestamp BETWEEN ? AND ?
            ORDER BY timestamp ASC;
            """,
            (start_dt.isoformat(), end_dt.isoformat()),
        )
        return [dict(r) for r in cursor.fetchall()]

    def query_by_location(self, location_name: str) -> List[Dict[str, Any]]:
        """Query indexed frames for a specific property zone."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT frame_id, timestamp, location_name, primary_log_message
            FROM frames
            WHERE location_name LIKE ?
            ORDER BY timestamp ASC;
            """,
            (f"%{location_name}%",),
        )
        return [dict(r) for r in cursor.fetchall()]

    def query_alerts(self, min_severity: Optional[str] = None) -> List[Dict[str, Any]]:
        """Query recorded security alerts, optionally filtered by severity."""
        cursor = self.conn.cursor()
        if min_severity:
            cursor.execute(
                """
                SELECT alert_id, frame_id, timestamp, severity, rule_name, message, location_name
                FROM alerts
                WHERE severity = ?
                ORDER BY timestamp ASC;
                """,
                (min_severity.upper(),),
            )
        else:
            cursor.execute(
                """
                SELECT alert_id, frame_id, timestamp, severity, rule_name, message, location_name
                FROM alerts
                ORDER BY timestamp ASC;
                """
            )
        return [dict(r) for r in cursor.fetchall()]

    def search_full_text(self, query_string: str) -> List[Dict[str, Any]]:
        """Execute full-text keyword search across frames and descriptions."""
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                """
                SELECT f.frame_id, f.timestamp, f.location_name, f.primary_log_message, f.raw_description
                FROM frames_fts fts
                JOIN frames f ON fts.frame_id = f.frame_id
                WHERE frames_fts MATCH ?
                ORDER BY rank;
                """,
                (query_string,),
            )
            return [dict(r) for r in cursor.fetchall()]
        except sqlite3.OperationalError:
            # Fallback to standard LIKE search
            pattern = f"%{query_string}%"
            cursor.execute(
                """
                SELECT frame_id, timestamp, location_name, primary_log_message, raw_description
                FROM frames
                WHERE raw_description LIKE ? OR primary_log_message LIKE ?
                ORDER BY timestamp ASC;
                """,
                (pattern, pattern),
            )
            return [dict(r) for r in cursor.fetchall()]

    def get_session_stats(self) -> Dict[str, Any]:
        """Aggregate high-level metrics for video session summarization."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) AS total_frames FROM frames;")
        total_frames = cursor.fetchone()["total_frames"]

        cursor.execute("SELECT COUNT(DISTINCT entity_id) AS unique_entities FROM entities;")
        unique_entities = cursor.fetchone()["unique_entities"]

        cursor.execute("SELECT COUNT(*) AS total_alerts FROM alerts;")
        total_alerts = cursor.fetchone()["total_alerts"]

        cursor.execute("SELECT DISTINCT location_name FROM frames;")
        locations = [r["location_name"] for r in cursor.fetchall()]

        cursor.execute("SELECT MIN(timestamp) as start_t, MAX(timestamp) as end_t FROM frames;")
        times = cursor.fetchone()

        return {
            "total_frames": total_frames,
            "unique_entities": unique_entities,
            "total_alerts": total_alerts,
            "monitored_locations": locations,
            "start_time": times["start_t"] if times else None,
            "end_time": times["end_t"] if times else None,
        }

    def close(self) -> None:
        """Close database connection."""
        self.conn.close()
