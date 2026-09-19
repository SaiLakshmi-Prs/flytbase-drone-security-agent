"""Main CLI Entrypoint for the FlytBase Drone Security Analyst Agent.

Provides commands for running the autonomous patrol simulation,
interactive natural language querying, and session summarization.
"""

from __future__ import annotations

import argparse
import datetime
import json
import logging
import sys
import time
from typing import List

from orchestrator import SecurityPipelineOrchestrator
from simulator import DroneSimulator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("main")


def run_demo(orchestrator: SecurityPipelineOrchestrator) -> None:
    """Run standard end-to-end autonomous patrol simulation."""
    sim = DroneSimulator()
    result = orchestrator.run_simulation(simulator=sim, time_delay_sec=0.05, verbose=True)

    print("\n" + "=" * 80)
    print(" SAMPLE NATURAL LANGUAGE QUERIES (BONUS FEATURE DEMO)")
    print("=" * 80)

    sample_questions = [
        "What objects were in the video?",
        "Show all truck events",
        "How many times did the blue Ford F150 enter?",
        "Were there any alerts at midnight?",
        "What happened at the main gate?",
    ]

    for q in sample_questions:
        print(f"\n[USER QUERY]: \"{q}\"")
        answer = orchestrator.answer_query(q)
        print(f"[AGENT ANSWER]:\n{answer}")

    print("\n" + "=" * 80)
    print(" PIPELINE BENCHMARK METRICS")
    print("=" * 80)
    print(f"Frames Ingested:        {result['total_frames']}")
    print(f"Alerts Dispatched:      {result['total_alerts']}")
    print(f"Average Frame Latency:  {result['pipeline_latency_ms_per_frame']:.3f} ms")
    print(f"Total Execution Time:   {result['total_elapsed_sec']:.3f} s")
    print("=" * 80)


def run_interactive(orchestrator: SecurityPipelineOrchestrator) -> None:
    """Interactive CLI REPL for querying the indexed drone property database."""
    print("=" * 80)
    print(" INTERACTIVE DRONE SECURITY ANALYST AGENT - Q&A CONSOLE ")
    print("=" * 80)
    print("Type your questions about property events, vehicles, personnel, or alerts.")
    print("Examples:")
    print("  - 'show all truck events'")
    print("  - 'what objects were in the video?'")
    print("  - 'were there any alerts at midnight?'")
    print("  - 'how many times did the blue Ford F150 enter?'")
    print("Type 'exit' or 'quit' to end.\n")

    # Ingest baseline simulation if database is fresh
    stats = orchestrator.indexer.get_session_stats()
    if stats["total_frames"] == 0:
        print("[System] Ingesting initial patrol mission into database...")
        orchestrator.run_simulation(verbose=False)
        print("[System] Patrol mission indexed. Ready for queries.\n")

    while True:
        try:
            query = input("\n[Query] > ").strip()
            if not query:
                continue
            if query.lower() in ["exit", "quit", "q"]:
                print("Exiting interactive console. Goodbye.")
                break

            # Help users who paste shell commands into the interactive prompt
            if query.startswith((".\\", "python", "pytest", "uv", "pip", "cd", "ls", "dir", "Get-")):
                print("\n[Notice]: You are currently inside the Agent Q&A REPL console.")
                print("  - To run terminal commands, type 'exit' first to return to PowerShell.")
                print("  - Inside this prompt, ask questions in natural language, for example:")
                print("      * 'show all truck events'")
                print("      * 'what objects were in the video?'")
                print("      * 'how many times did the blue Ford F150 enter?'")
                continue

            response = orchestrator.answer_query(query)
            print(f"\n[Agent]:\n{response}")

        except (KeyboardInterrupt, EOFError):
            print("\nExiting interactive console. Goodbye.")
            break


def run_benchmark(iterations: int = 100) -> None:
    """Run stress benchmark measuring ingestion, extraction, and indexing throughput."""
    print(f"Starting performance benchmark across {iterations} frames using in-memory database...")
    orch = SecurityPipelineOrchestrator(db_path=":memory:")
    sim = DroneSimulator()
    frames = sim.generate_scenario_frames()

    t_start = time.perf_counter()
    count = 0
    while count < iterations:
        for f in frames:
            p = orch.perception_engine.parse_frame(f)
            orch.agent.process_frame(f, p)
            count += 1
            if count >= iterations:
                break
    t_total = time.perf_counter() - t_start

    fps = count / t_total
    latency_ms = (t_total / count) * 1000.0

    print("=" * 50)
    print(" BENCHMARK RESULTS")
    print("=" * 50)
    print(f"Frames Processed:   {count}")
    print(f"Total Time:         {t_total:.4f} s")
    print(f"Throughput:         {fps:.1f} FPS (Target: >= 30 FPS)")
    print(f"Latency Per Frame:  {latency_ms:.3f} ms")
    print("=" * 50)


def main() -> None:
    """Parse CLI arguments and dispatch execution."""
    parser = argparse.ArgumentParser(
        description="FlytBase Drone Security Analyst Agent - Prototype CLI"
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run end-to-end patrol simulation with sample queries and metrics",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Launch interactive Natural Language Q&A prompt",
    )
    parser.add_argument(
        "--query",
        type=str,
        help="Execute a single natural language query and print the answer",
    )
    parser.add_argument(
        "--benchmark",
        action="store_true",
        help="Execute performance and throughput benchmark",
    )
    parser.add_argument(
        "--db",
        type=str,
        default="drone_security.db",
        help="Path to SQLite database file (default: drone_security.db)",
    )

    args = parser.parse_args()

    # Default to demo if no specific mode selected
    if not (args.demo or args.interactive or args.query or args.benchmark):
        args.demo = True

    if args.benchmark:
        run_benchmark()
        return

    orchestrator = SecurityPipelineOrchestrator(db_path=args.db)

    if args.demo:
        run_demo(orchestrator)
    elif args.interactive:
        run_interactive(orchestrator)
    elif args.query:
        # Ensure database is primed
        stats = orchestrator.indexer.get_session_stats()
        if stats["total_frames"] == 0:
            orchestrator.run_simulation(verbose=False)
        ans = orchestrator.answer_query(args.query)
        print(f"\n[Query]: {args.query}")
        print(f"[Agent Answer]:\n{ans}\n")


if __name__ == "__main__":
    main()
