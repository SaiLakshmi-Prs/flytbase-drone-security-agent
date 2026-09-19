"""Drone Telemetry and Video Ingestion Simulator.

Simulates synchronized drone telemetry (GPS coordinates, altitude, battery status,
flight phase) along with visual video frame descriptions over a monitored property.
"""

from __future__ import annotations

import datetime
from dataclasses import asdict, dataclass
import logging
from typing import Any, Dict, Generator, List, Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TelemetryData:
    """Represents real-time telemetry emitted by the autonomous docked drone."""

    timestamp: datetime.datetime
    latitude: float
    longitude: float
    altitude_m: float
    battery_percent: float
    heading_deg: float
    velocity_mps: float
    dock_status: str  # "DOCKED", "AIRBORNE", "RETURNING", "CHARGING"
    location_name: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert telemetry instance to dictionary representation."""
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        return data


@dataclass(frozen=True)
class VideoFrame:
    """Represents a synchronized video frame with metadata and raw visual description."""

    frame_id: int
    timestamp: datetime.datetime
    telemetry: TelemetryData
    raw_description: str
    camera_fov: str = "WIDE_ANGLE_RGB"
    lighting_condition: str = "DAYLIGHT"  # "DAYLIGHT", "DUSK", "NIGHT_INFRARED"

    def to_dict(self) -> Dict[str, Any]:
        """Convert frame instance to dictionary representation."""
        return {
            "frame_id": self.frame_id,
            "timestamp": self.timestamp.isoformat(),
            "telemetry": self.telemetry.to_dict(),
            "raw_description": self.raw_description,
            "camera_fov": self.camera_fov,
            "lighting_condition": self.lighting_condition,
        }


class DroneSimulator:
    """Simulates realistic telemetry and video frame streaming for perimeter security.

    Provides pre-programmed operational scenarios that satisfy core assignment
    requirements, including repeat vehicle detection, midnight loitering, and safety events.
    """

    BASE_LATITUDE: float = 37.774929
    BASE_LONGITUDE: float = -122.419416

    PROPERTY_WAYPOINTS = {
        "Docking Station": (37.774929, -122.419416, 0.0),
        "Garage": (37.775150, -122.418900, 18.5),
        "Loading Bay": (37.775400, -122.418200, 20.0),
        "Perimeter Fence North": (37.775800, -122.419100, 22.0),
        "Main Gate": (37.774800, -122.420200, 15.0),
        "North Gate": (37.775950, -122.419800, 16.5),
        "Fuel Depot": (37.774500, -122.418500, 19.0),
    }

    def __init__(self, base_date: Optional[datetime.date] = None) -> None:
        """Initialize the simulator with a target patrol date.

        Args:
            base_date: Base calendar day for the mission scenario (defaults to today).
        """
        self.base_date = base_date or datetime.date(2026, 9, 18)

    def _make_dt(self, hour: int, minute: int, second: int = 0) -> datetime.datetime:
        """Construct a datetime object anchored to the simulation date."""
        return datetime.datetime(
            self.base_date.year,
            self.base_date.month,
            self.base_date.day,
            hour,
            minute,
            second,
        )

    def generate_scenario_frames(self) -> List[VideoFrame]:
        """Generate a curated, chronologically sequenced scenario of 12 security frames.

        This scenario covers:
        - Daytime patrols: First sighting of a blue Ford F150 at the garage at 12:00.
        - Commercial deliveries at the Loading Bay.
        - Repeat entry: A second sighting of the blue Ford F150 at the garage at 16:15.
        - Night patrol: Midnight perimeter loitering by an unauthorized individual at Main Gate (00:01 - 00:03).
        - Authorized guard patrol at North Gate.
        - Critical telemetry event: Drone low battery off-dock forcing RTH.

        Returns:
            List of VideoFrame objects with synchronized telemetry.
        """
        raw_events = [
            # Frame 1: Departure & first daytime patrol
            {
                "time": self._make_dt(11, 58, 0),
                "location": "Docking Station",
                "alt": 2.0,
                "battery": 98.0,
                "heading": 45.0,
                "velocity": 1.5,
                "dock_status": "AIRBORNE",
                "lighting": "DAYLIGHT",
                "desc": "Drone takes off from Docking Station. Sensor calibration complete, clear perimeter view.",
            },
            # Frame 2: Blue Ford F150 spotted at garage (12:00)
            {
                "time": self._make_dt(12, 0, 0),
                "location": "Garage",
                "alt": 18.5,
                "battery": 95.0,
                "heading": 88.0,
                "velocity": 3.2,
                "dock_status": "AIRBORNE",
                "lighting": "DAYLIGHT",
                "desc": "Blue Ford F150 spotted at garage entrance. Vehicle engine idling near service door.",
            },
            # Frame 3: Delivery van at loading bay
            {
                "time": self._make_dt(12, 15, 0),
                "location": "Loading Bay",
                "alt": 20.0,
                "battery": 91.0,
                "heading": 130.0,
                "velocity": 0.0,
                "dock_status": "AIRBORNE",
                "lighting": "DAYLIGHT",
                "desc": "White Mercedes Sprinter delivery van parked at loading dock. Cargo bay doors open, worker unloading boxes.",
            },
            # Frame 4: North Perimeter fence check
            {
                "time": self._make_dt(14, 30, 0),
                "location": "Perimeter Fence North",
                "alt": 22.0,
                "battery": 84.0,
                "heading": 270.0,
                "velocity": 4.5,
                "dock_status": "AIRBORNE",
                "lighting": "DAYLIGHT",
                "desc": "North fence line clear. Tree branches slightly swaying, barbed wire intact with no breach indications.",
            },
            # Frame 5: Second entry of Blue Ford F150 (16:15) - Multiple visit context
            {
                "time": self._make_dt(16, 15, 0),
                "location": "Garage",
                "alt": 19.0,
                "battery": 78.0,
                "heading": 92.0,
                "velocity": 2.1,
                "dock_status": "AIRBORNE",
                "lighting": "DAYLIGHT",
                "desc": "Blue Ford F150 truck re-enters property, parked in rear garage lot near employee exit.",
            },
            # Frame 6: Fuel Depot routine inspection
            {
                "time": self._make_dt(18, 45, 0),
                "location": "Fuel Depot",
                "alt": 17.0,
                "battery": 69.0,
                "heading": 180.0,
                "velocity": 0.5,
                "dock_status": "AIRBORNE",
                "lighting": "DUSK",
                "desc": "Fuel depot containment area secure. Pressure gauges nominal, no personnel or vehicles detected.",
            },
            # Frame 7: Midnight patrol begins (23:55)
            {
                "time": self._make_dt(23, 55, 0),
                "location": "Main Gate",
                "alt": 15.0,
                "battery": 60.0,
                "heading": 210.0,
                "velocity": 3.0,
                "dock_status": "AIRBORNE",
                "lighting": "NIGHT_INFRARED",
                "desc": "Thermal camera active. Main gate locked, floodlights operational, asphalt cool.",
            },
            # Frame 8: Person spotted at main gate (00:01) - Loitering frame 1
            {
                "time": self._make_dt(0, 1, 0) + datetime.timedelta(days=1),
                "location": "Main Gate",
                "alt": 15.0,
                "battery": 57.0,
                "heading": 215.0,
                "velocity": 0.8,
                "dock_status": "AIRBORNE",
                "lighting": "NIGHT_INFRARED",
                "desc": "Person loitering at main gate, 00:01. Subject wearing dark hooded jacket, standing near pedestrian turnstile.",
            },
            # Frame 9: Person still loitering at main gate (00:02) - Loitering frame 2
            {
                "time": self._make_dt(0, 2, 0) + datetime.timedelta(days=1),
                "location": "Main Gate",
                "alt": 14.5,
                "battery": 55.0,
                "heading": 218.0,
                "velocity": 0.2,
                "dock_status": "AIRBORNE",
                "lighting": "NIGHT_INFRARED",
                "desc": "Person loitering at main gate continues surveillance. Subject peering through gate slats, carrying unidentified backpack.",
            },
            # Frame 10: Person attempting gate breach (00:03) - Loitering frame 3 (Critical Alert)
            {
                "time": self._make_dt(0, 3, 0) + datetime.timedelta(days=1),
                "location": "Main Gate",
                "alt": 14.0,
                "battery": 52.0,
                "heading": 220.0,
                "velocity": 0.0,
                "dock_status": "AIRBORNE",
                "lighting": "NIGHT_INFRARED",
                "desc": "Unauthorized person attempting manual override on main gate keypad, suspicious loitering over 3 minutes after midnight.",
            },
            # Frame 11: Security officer patrol at North Gate (00:06) - Authorized personnel
            {
                "time": self._make_dt(0, 6, 0) + datetime.timedelta(days=1),
                "location": "North Gate",
                "alt": 16.0,
                "battery": 46.0,
                "heading": 350.0,
                "velocity": 2.4,
                "dock_status": "AIRBORNE",
                "lighting": "NIGHT_INFRARED",
                "desc": "Uniformed security guard on foot patrol at North Gate carrying tactical flashlight, scanning ID badge at checkpoint.",
            },
            # Frame 12: Low battery safety alert trigger (00:10)
            {
                "time": self._make_dt(0, 10, 0) + datetime.timedelta(days=1),
                "location": "Fuel Depot",
                "alt": 19.0,
                "battery": 16.5,  # Below 20% critical threshold while AIRBORNE
                "heading": 175.0,
                "velocity": 5.0,
                "dock_status": "RETURNING",
                "lighting": "NIGHT_INFRARED",
                "desc": "Drone initiated Return-To-Home (RTH). Telemetry warning: battery level at 16.5% while airborne over Fuel Depot.",
            },
        ]

        frames: List[VideoFrame] = []
        for idx, event in enumerate(raw_events, start=1):
            loc_name = str(event["location"])
            lat, lon, def_alt = self.PROPERTY_WAYPOINTS.get(
                loc_name, (self.BASE_LATITUDE, self.BASE_LONGITUDE, 15.0)
            )
            alt = float(event.get("alt", def_alt))

            telemetry = TelemetryData(
                timestamp=event["time"],  # type: ignore[arg-type]
                latitude=lat,
                longitude=lon,
                altitude_m=alt,
                battery_percent=float(event["battery"]),
                heading_deg=float(event["heading"]),
                velocity_mps=float(event["velocity"]),
                dock_status=str(event["dock_status"]),
                location_name=loc_name,
            )

            frame = VideoFrame(
                frame_id=idx,
                timestamp=event["time"],  # type: ignore[arg-type]
                telemetry=telemetry,
                raw_description=str(event["desc"]),
                camera_fov="WIDE_ANGLE_RGB" if event["lighting"] == "DAYLIGHT" else "THERMAL_IR",
                lighting_condition=str(event["lighting"]),
            )
            frames.append(frame)

        return frames

    def stream(self) -> Generator[VideoFrame, None, None]:
        """Yield frames sequentially as a real-time generator."""
        for frame in self.generate_scenario_frames():
            yield frame
