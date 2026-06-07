# agent/emit_event.py
import boto3
import json
import sys
from datetime import datetime

EVENT_BUS_NAME = "vm-resize-agent-bus"
REGION         = "us-east-1"

def emit(status: str, steps_completed: int, steps_total: int,
         failed_step: str = None, duration_minutes: int = 0):

    client = boto3.client("events", region_name=REGION)

    detail = {
        "status":           status,
        "pipeline":         "data-loader",
        "steps_completed":  steps_completed,
        "steps_total":      steps_total,
        "duration_minutes": duration_minutes,
        "failed_step":      failed_step,
        "timestamp": datetime.now(datetime.UTC).isoformat()
    }

    response = client.put_events(
        Entries=[{
            "EventBusName": EVENT_BUS_NAME,
            "Source":       "vm.pipeline",
            "DetailType":   "PipelineComplete",
            "Detail":       json.dumps(detail)
        }]
    )

    failed = response.get("FailedEntryCount", 0)
    if failed > 0:
        print(f"[ERROR] Event failed to send: {response}")
        sys.exit(1)

    print(f"[OK] Event sent → status={status}")

if __name__ == "__main__":
    # usage: python emit_event.py SUCCESS 5 5 120
    # usage: python emit_event.py FAILURE 3 5 60 build_forecasts
    status           = sys.argv[1]
    steps_completed  = int(sys.argv[2])
    steps_total      = int(sys.argv[3])
    duration_minutes = int(sys.argv[4])
    failed_step      = sys.argv[5] if len(sys.argv) > 5 else None

    emit(status, steps_completed, steps_total, failed_step, duration_minutes)