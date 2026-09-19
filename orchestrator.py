"""Pipeline Orchestrator for the Drone Security Analyst Agent.

Coordinates data ingestion from the simulator, real-time perception inference,
database indexing, and agentic threat alerting into a unified operational stream.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Dict, List, Optional

from agent import DroneSecurityAnalystAgent, SecurityAlert
from indexer import FrameIndexer
from perception import BasePerceptionEngine, EdgeRulePerceptionEngine, PerceptionResult
from simulator import DroneSimulator, VideoFrame

logger = logging.getLogger(__name__)


class SecurityPipelineOrchestrator:
    """Orchestrates end-to-end ingestion, perception, indexing, and alerting."""

    def __init__(
        self,
        db_path: str = "drone_security.db",
        perception_engine: Optional[BasePerceptionEngine] = None,
        log_callback: Optional[Callable[[str], None]] = None,
        alert_callback: Optional[Callable[[SecurityAlert], None]] = None,
    ) -> None:
        """Initialize pipeline with storage, perception, and agent components."""
        self.indexer = FrameIndexer(db_path=db_path)
        self.perception_engine = perception_engine or EdgeRulePerceptionEngine()
        self.agent = DroneSecurityAnalystAgent(self.indexer)
        self.log_callback = log_callback or (lambda msg: None)
        self.alert_callback = alert_callback or (lambda alert: None)

        # Performance tracking
        self.processed_frame_count: int = 0
        self.total_pipeline_time_sec: float = 0.0

    def run_simulation(
        self,
        simulator: Optional[DroneSimulator] = None,
        time_delay_sec: float = 0.0,
        verbose: bool = True,
    ) -> Dict[str, Any]:
        """Execute a full simulated drone security patrol mission.

        Args:
            simulator: Simulator instance producing frames.
            time_delay_sec: Delay between frames to simulate real-time streaming.
            verbose: If True, prints formatted console logs and alerts.

        Returns:
            Dictionary containing mission execution metrics, session summary, and all alerts.
        """
        sim = simulator or DroneSimulator()
        frames = sim.generate_scenario_frames()

        mission_alerts: List[SecurityAlert] = []
        mission_logs: List[str] = []

        if verbose:
            print("=" * 80)
            print(" FLYTBASE DRONE SECURITY ANALYST AGENT - AUTONOMOUS PATROL PIPELINE ")
            print("=" * 80)

        start_wall_time = time.perf_counter()

        for frame in frames:
            t0 = time.perf_counter()

            # 1. Perception Layer
            perception_result = self.perception_engine.parse_frame(frame)

            # 2. Agent Processing & Indexing
            new_alerts = self.agent.process_frame(frame, perception_result)
            mission_alerts.extend(new_alerts)

            t1 = time.perf_counter()
            self.processed_frame_count += 1
            self.total_pipeline_time_sec += (t1 - t0)

            # 3. Formatted Console Logging (Matching Expected Sample Output)
            log_line = (
                f"[LOG] {frame.timestamp.strftime('%H:%M')} | Frame #{frame.frame_id:02d} "
                f"({frame.telemetry.location_name}) -> {perception_result.primary_log_message}"
            )
            mission_logs.append(log_line)
            self.log_callback(log_line)

            if verbose:
                print(log_line)

            # 4. Immediate Real-Time Alerts
            for alert in new_alerts:
                alert_line = (
                    f"  >>> [{alert.severity}] {alert.format_canonical()} "
                    f"[Rule: {alert.rule_name}]"
                )
                self.alert_callback(alert)
                if verbose:
                    print(alert_line)

            if time_delay_sec > 0:
                time.sleep(time_delay_sec)

        total_elapsed = time.perf_counter() - start_wall_time
        summary = self.agent.generate_session_summary()

        if verbose:
            print("-" * 80)
            print("PATROL SUMMARY & EXECUTIVE BRIEF:")
            print(summary["one_sentence_summary"])
            print("-" * 80)

        return {
            "total_frames": len(frames),
            "total_alerts": len(mission_alerts),
            "alerts": mission_alerts,
            "logs": mission_logs,
            "session_summary": summary,
            "pipeline_latency_ms_per_frame": (
                (self.total_pipeline_time_sec / max(1, self.processed_frame_count)) * 1000.0
            ),
            "total_elapsed_sec": total_elapsed,
        }

    def answer_query(self, query: str) -> str:
        """Route natural language questions directly to the agent's reasoning engine."""
        return self.agent.answer_question(query)
