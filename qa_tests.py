"""Comprehensive QA Test Suite for the Drone Security Analyst Agent.

Uses Python's built-in unittest framework to validate simulator data models,
perception parsing accuracy, cross-domain SQLite indexing, agentic rule evaluation,
behavioral tracking, session summarization, and natural language Q&A.
"""

from __future__ import annotations

import datetime
import unittest

from agent import DroneSecurityAnalystAgent, EntityStateTracker, SecurityAlert
from indexer import FrameIndexer
from perception import DetectedEntity, EdgeRulePerceptionEngine, PerceptionResult
from simulator import DroneSimulator, TelemetryData, VideoFrame


class TestDroneSimulator(unittest.TestCase):
    """Unit tests for drone telemetry and synchronized video frame simulation."""

    def setUp(self) -> None:
        self.simulator = DroneSimulator(base_date=datetime.date(2026, 9, 18))

    def test_scenario_generation_completeness(self) -> None:
        """Verify scenario generates 12 frames with valid synchronized telemetry."""
        frames = self.simulator.generate_scenario_frames()
        self.assertEqual(len(frames), 12)

        prev_time = datetime.datetime.min
        for frame in frames:
            self.assertIsInstance(frame, VideoFrame)
            self.assertIsInstance(frame.telemetry, TelemetryData)
            # Monotonic time progression
            self.assertGreater(frame.timestamp, prev_time)
            prev_time = frame.timestamp
            # Telemetry bounds
            self.assertGreaterEqual(frame.telemetry.battery_percent, 0.0)
            self.assertLessEqual(frame.telemetry.battery_percent, 100.0)
            self.assertGreaterEqual(frame.telemetry.altitude_m, 0.0)
            self.assertGreaterEqual(frame.telemetry.heading_deg, 0.0)
            self.assertLessEqual(frame.telemetry.heading_deg, 360.0)
            self.assertTrue(len(frame.raw_description) > 5)

    def test_frame_serialization(self) -> None:
        """Verify frame dictionary conversion produces serializable output."""
        frame = self.simulator.generate_scenario_frames()[0]
        data = frame.to_dict()
        self.assertEqual(data["frame_id"], 1)
        self.assertIn("timestamp", data)
        self.assertIn("telemetry", data)
        self.assertEqual(data["telemetry"]["dock_status"], "AIRBORNE")


class TestPerceptionEngine(unittest.TestCase):
    """Unit tests for entity extraction, attribute parsing, and threat heuristics."""

    def setUp(self) -> None:
        self.engine = EdgeRulePerceptionEngine()
        self.base_time = datetime.datetime(2026, 9, 18, 12, 0, 0)

    def _make_dummy_frame(
        self, desc: str, hour: int = 12, minute: int = 0, battery: float = 90.0, loc: str = "Garage"
    ) -> VideoFrame:
        dt = datetime.datetime(2026, 9, 18, hour, minute, 0)
        tel = TelemetryData(
            timestamp=dt,
            latitude=37.77,
            longitude=-122.41,
            altitude_m=18.0,
            battery_percent=battery,
            heading_deg=90.0,
            velocity_mps=2.0,
            dock_status="AIRBORNE",
            location_name=loc,
        )
        return VideoFrame(
            frame_id=101,
            timestamp=dt,
            telemetry=tel,
            raw_description=desc,
        )

    def test_vehicle_extraction_blue_ford_f150(self) -> None:
        """Verify extraction of Blue Ford F150 with make, model, color attributes."""
        frame = self._make_dummy_frame(
            "Blue Ford F150 spotted at garage entrance. Vehicle engine idling."
        )
        res = self.engine.parse_frame(frame)
        self.assertEqual(len(res.entities), 1)
        entity = res.entities[0]
        self.assertEqual(entity.category, "vehicle")
        self.assertEqual(entity.attributes.get("color"), "Blue")
        self.assertEqual(entity.attributes.get("make"), "Ford")
        self.assertEqual(entity.attributes.get("model"), "F150")
        self.assertEqual(entity.attributes.get("vehicle_type"), "truck")
        self.assertEqual(res.primary_log_message, "Blue Ford F150 spotted at garage, 12:00.")

    def test_delivery_van_extraction(self) -> None:
        """Verify extraction of delivery van and worker."""
        frame = self._make_dummy_frame(
            "White Mercedes Sprinter delivery van parked at loading dock. Cargo bay doors open, worker unloading boxes.",
            loc="Loading Bay",
        )
        res = self.engine.parse_frame(frame)
        labels = [e.label for e in res.entities]
        self.assertTrue(any("Mercedes" in l for l in labels))
        self.assertTrue(any("worker" in l.lower() for l in labels))

    def test_midnight_loitering_extraction(self) -> None:
        """Verify after-hours loitering person detection and threat classification."""
        frame = self._make_dummy_frame(
            "Person loitering at main gate, 00:01. Subject wearing dark hooded jacket.",
            hour=0,
            minute=1,
            loc="Main Gate",
        )
        res = self.engine.parse_frame(frame)
        self.assertEqual(len(res.entities), 1)
        entity = res.entities[0]
        self.assertEqual(entity.category, "person")
        self.assertTrue(entity.attributes.get("loitering"))
        self.assertTrue(entity.attributes.get("after_hours"))
        self.assertEqual(entity.threat_indicator, "ALERT")
        self.assertEqual(res.primary_log_message, "Person loitering at main gate, 00:01.")

    def test_negation_handling(self) -> None:
        """Verify engine does not extract entities when negative assertion is present."""
        frame = self._make_dummy_frame(
            "Fuel depot containment area secure. Pressure gauges nominal, no personnel or vehicles detected.",
            loc="Fuel Depot",
        )
        res = self.engine.parse_frame(frame)
        self.assertEqual(len(res.entities), 0)

    def test_critical_battery_hazard(self) -> None:
        """Verify low battery (< 20%) while airborne produces telemetry hazard entity."""
        frame = self._make_dummy_frame(
            "Routine surveillance patrol over fuel depot.",
            battery=16.5,
            loc="Fuel Depot",
        )
        res = self.engine.parse_frame(frame)
        self.assertEqual(len(res.entities), 1)
        entity = res.entities[0]
        self.assertEqual(entity.category, "telemetry_hazard")
        self.assertEqual(entity.threat_indicator, "CRITICAL")


class TestFrameIndexer(unittest.TestCase):
    """Unit tests for SQLite persistent cross-domain frame indexing and retrieval."""

    def setUp(self) -> None:
        self.indexer = FrameIndexer(":memory:")
        self.simulator = DroneSimulator()
        self.engine = EdgeRulePerceptionEngine()

        # Prime database with 12 scenario frames
        for frame in self.simulator.generate_scenario_frames():
            res = self.engine.parse_frame(frame)
            self.indexer.index_frame(frame, res)

    def tearDown(self) -> None:
        self.indexer.close()

    def test_frame_counts_and_stats(self) -> None:
        """Verify all frames and entities are indexed."""
        stats = self.indexer.get_session_stats()
        self.assertEqual(stats["total_frames"], 12)
        self.assertGreaterEqual(stats["unique_entities"], 5)
        self.assertIn("Garage", stats["monitored_locations"])
        self.assertIn("Main Gate", stats["monitored_locations"])

    def test_query_truck_events(self) -> None:
        """Verify query_truck_events returns both sightings of the blue Ford F150."""
        trucks = self.indexer.query_truck_events()
        self.assertEqual(len(trucks), 2)
        frame_ids = [t["frame_id"] for t in trucks]
        self.assertIn(2, frame_ids)
        self.assertIn(5, frame_ids)

    def test_query_by_time_range(self) -> None:
        """Verify querying frames within a time window (e.g., midnight to 00:05)."""
        start_t = datetime.datetime(2026, 9, 19, 0, 0, 0)
        end_t = datetime.datetime(2026, 9, 19, 0, 5, 0)
        results = self.indexer.query_by_time_range(start_t, end_t)
        # Frames 8, 9, 10 occur at 00:01, 00:02, 00:03
        self.assertEqual(len(results), 3)

    def test_query_by_location(self) -> None:
        """Verify geospatial location filtering."""
        garage_events = self.indexer.query_by_location("Garage")
        self.assertEqual(len(garage_events), 2)
        main_gate_events = self.indexer.query_by_location("Main Gate")
        self.assertEqual(len(main_gate_events), 4)

    def test_full_text_search(self) -> None:
        """Verify full-text keyword retrieval."""
        matches = self.indexer.search_full_text("Sprinter")
        self.assertGreaterEqual(len(matches), 1)
        self.assertEqual(matches[0]["location_name"], "Loading Bay")


class TestDroneSecurityAnalystAgent(unittest.TestCase):
    """Unit tests for agentic reasoning, alerting, loitering tracking, and Q&A."""

    def setUp(self) -> None:
        self.indexer = FrameIndexer(":memory:")
        self.engine = EdgeRulePerceptionEngine()
        self.agent = DroneSecurityAnalystAgent(self.indexer)
        self.simulator = DroneSimulator()
        self.frames = self.simulator.generate_scenario_frames()

    def tearDown(self) -> None:
        self.indexer.close()

    def test_full_pipeline_alerts(self) -> None:
        """Verify agent triggers all required security and safety alerts."""
        all_alerts: List[SecurityAlert] = []
        for frame in self.frames:
            res = self.engine.parse_frame(frame)
            alerts = self.agent.process_frame(frame, res)
            all_alerts.extend(alerts)

        self.assertEqual(len(all_alerts), 5)

        rule_names = [a.rule_name for a in all_alerts]
        self.assertIn("REPEAT_VEHICLE_ACTIVITY", rule_names)
        self.assertIn("AFTER_HOURS_LOITERING", rule_names)
        self.assertIn("UNAUTHORIZED_PERIMETER_BREACH", rule_names)
        self.assertIn("DRONE_LOW_BATTERY_RTH", rule_names)

        # Check canonical format of the midnight loitering alert
        midnight_alert = [a for a in all_alerts if a.frame_id == 8][0]
        self.assertEqual(
            midnight_alert.format_canonical(),
            "Alert: Person loitering at main gate, 00:01",
        )

    def test_repeat_vehicle_visit_tracking(self) -> None:
        """Verify agent tracks visit counts and notes that Blue Ford F150 entered twice today."""
        for frame in self.frames:
            res = self.engine.parse_frame(frame)
            self.agent.process_frame(frame, res)

        visits = self.agent.state_tracker.get_visit_count("vehicle:ford_f150_blue")
        self.assertEqual(visits, 2)

    def test_bonus_session_summarization(self) -> None:
        """Verify bonus 1-sentence video session summary generation."""
        for frame in self.frames:
            res = self.engine.parse_frame(frame)
            self.agent.process_frame(frame, res)

        summary = self.agent.generate_session_summary()
        self.assertIn("one_sentence_summary", summary)
        text = summary["one_sentence_summary"]

        self.assertIn("12 monitored patrol frames", text)
        self.assertIn("blue Ford F150 entered twice", text)
        self.assertIn("midnight loitering at Main Gate", text)
        self.assertIn("low-battery RTH procedure", text)

    def test_bonus_natural_language_qa(self) -> None:
        """Verify bonus interactive Q&A capability over indexed property events."""
        for frame in self.frames:
            res = self.engine.parse_frame(frame)
            self.agent.process_frame(frame, res)

        # Test Q1: What objects were in the video?
        ans1 = self.agent.answer_question("What objects were in the video?")
        self.assertIn("Blue Ford F150", ans1)
        self.assertIn("Person loitering", ans1)

        # Test Q2: Show all truck events
        ans2 = self.agent.answer_question("Show all truck events")
        self.assertIn("Found 2 indexed truck event(s)", ans2)
        self.assertIn("Frame #2", ans2)
        self.assertIn("Frame #5", ans2)

        # Test Q3: How many times did the blue Ford F150 enter?
        ans3 = self.agent.answer_question("How many times did the blue Ford F150 enter?")
        self.assertIn("entered 2 times today", ans3)

        # Test Q4: Were there any alerts at midnight?
        ans4 = self.agent.answer_question("Were there any alerts at midnight?")
        self.assertIn("Detected 4 alert(s)", ans4)
        self.assertIn("00:01 at Main Gate", ans4)


if __name__ == "__main__":
    unittest.main()
