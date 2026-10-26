#!/usr/bin/env python3
"""
DeepClaw Nova - Main Unified System Controller & Voice Agent CLI
Designed for Mac M5 (32GB Unified Memory Architecture).
"""

import sys
import os
import argparse
import time
import shutil
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent))

import config
from core.telemetry import get_system_metrics
from core.throttling import UnifiedMemoryGovernor
from core.residency import ModelResidencyManager
from memory.compactor import ContinuousCompactor
from memory.db import MemoryStore
from training.trainer import ModelTrainer
from tools.system import clean_system_caches, get_system_health
from voice.assistant import NovaVoiceAssistant
from core.job_store import JobStore

def cmd_status():
    metrics = get_system_metrics()
    health = get_system_health()
    residency = ModelResidencyManager()
    store = MemoryStore()

    print("\033[1;36m====================================================================\033[0m")
    print("\033[1;37m 🐺 DEEPCLAW NOVA · APPLE SILICON M5 MISSION CONTROL\033[0m")
    print("\033[1;36m====================================================================\033[0m")
    print(f"\033[1;33m[UNIFIED MEMORY & HARDWARE (32GB UMA)]\033[0m")
    print(f"  • Host Unified RAM : {metrics['used_ram_mb']:.1f} MB used / {metrics['total_ram_mb']:.1f} MB total ({metrics['avail_ram_mb']:.1f} MB free)")
    print(f"  • macOS Swap Space : {metrics['swap_used_mb']:.1f} MB active")
    print(f"  • Disk Free Space  : {health['disk_free_gb']} GB / {health['disk_total_gb']} GB")
    
    print(f"\033[1;34m[NEURAL MODEL RESIDENCY]\033[0m")
    is_res = residency.is_model_loaded()
    res_str = "\033[1;32m● RESIDENT (LOCKED IN RAM)\033[0m" if is_res else "\033[1;31m○ STANDBY (NOT PINNED)\033[0m"
    print(f"  • Model Name       : {config.DEFAULT_MODEL}")
    print(f"  • Residency Status : {res_str}")
    print(f"  • Engine Endpoint  : {config.OLLAMA_URL}")

    print(f"\033[1;35m[KNOWLEDGE & MEMORY RETENTION]\033[0m")
    with store.get_connection() as conn:
        m_count = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
        f_count = conn.execute("SELECT COUNT(*) FROM file_compaction").fetchone()[0]
        s_count = conn.execute("SELECT COUNT(*) FROM skills_ledger").fetchone()[0]
        t_count = conn.execute("SELECT COUNT(*) FROM training_traces").fetchone()[0]

    print(f"  • Synthesized Memories : {m_count} records")
    print(f"  • Compacted Documents  : {f_count} files")
    print(f"  • Self-Authored Skills : {s_count} active tools")
    print(f"  • Execution Traces     : {t_count} training samples")
    print("\033[1;36m====================================================================\033[0m")

def cmd_ask(prompt: str, voice: bool = True):
    assistant = NovaVoiceAssistant()
    print(f"\n\033[1;34mUser:\033[0m {prompt}")
    ans = assistant.process_command(prompt, voice_output=voice)
    print(f"\033[1;32mNova:\033[0m {ans}\n")

def cmd_live():
    print("\033[1;35mStarting DeepClaw Nova 24/7 Live Resident Voice Assistant...\033[0m")
    assistant = NovaVoiceAssistant()
    assistant.residency.start_residency_watchdog()
    compactor = ContinuousCompactor()

    assistant.tts.speak("DeepClaw Nova online. I am listening.")
    print("Nova is active. Speak commands or press Ctrl+C to stop.")

    # Background periodic compaction & memory sweep loop
    last_sweep = time.time()
    try:
        while True:
            # Run background sweep every 5 minutes under asymptotic backpressure
            if time.time() - last_sweep > 300:
                compactor.run_sweep()
                compactor.synthesize_round()
                last_sweep = time.time()
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\nNova stopping gracefully.")
        assistant.residency.stop_residency_watchdog()

def cmd_train():
    print("\033[1;33mInitiating On-Device Training Round via Apple Metal...\033[0m")
    trainer = ModelTrainer()
    res = trainer.train_lora_round()
    print(f"Training Result: {res['status']}")
    if "duration_seconds" in res:
        print(f"Trained {res.get('traces_trained', 0)} traces in {res['duration_seconds']:.2f}s.")
    if "adapter_path" in res:
        print(f"LoRA Adapter saved to: {res['adapter_path']}")

def cmd_clean():
    res = clean_system_caches()
    print(f"Reclaimed {res['reclaimed_mb']:.2f} MB from system caches.")

def cmd_jobs(status=None, limit=50):
    store = JobStore()
    jobs = store.list_jobs(limit=limit, status=status)
    if not jobs:
        print("No jobs found.")
        return
    print(f"{'JOB ID':<18} {'STATUS':<16} {'CLASS':<12} {'OWNER':<10} {'RETRIES':<8}")
    print("-" * 70)
    for j in jobs:
        print(f"{j['job_id']:<18} {j['status']:<16} {j['resource_class']:<12} {j['owner']:<10} {j['retry_count']:<8}")

def main():
    parser = argparse.ArgumentParser(description="DeepClaw Nova System Controller (Mac M5)")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("status", help="Display hardware, memory, and model status")
    subparsers.add_parser("live", help="Run 24/7 live voice assistant loop")
    subparsers.add_parser("train", help="Run on-device fine-tuning round")
    subparsers.add_parser("clean", help="Clean developer and app caches")
    jobs_p = subparsers.add_parser("jobs", help="List governor jobs")
    jobs_p.add_argument("--status", type=str, default=None)
    jobs_p.add_argument("--limit", type=int, default=50)

    ask_p = subparsers.add_parser("ask", help="Send a command or prompt")
    ask_p.add_argument("query", type=str, help="Text instruction for Nova")
    ask_p.add_argument("--no-voice", action="store_true", help="Disable voice speech output")

    args = parser.parse_args()
    if args.command == "status" or not args.command:
        cmd_status()
    elif args.command == "ask":
        cmd_ask(args.query, voice=not args.no_voice)
    elif args.command == "live":
        cmd_live()
    elif args.command == "train":
        cmd_train()
    elif args.command == "clean":
        cmd_clean()
    elif args.command == "jobs":
        cmd_jobs(status=args.status, limit=args.limit)

if __name__ == "__main__":
    main()
