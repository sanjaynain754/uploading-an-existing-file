"""
Demo script: submits a task and polls until it reaches awaiting_approval,
then auto-approves it.
"""
import time
import httpx

BASE = "http://localhost:8000"


def main():
    print("📝 Submitting task...")
    r = httpx.post(f"{BASE}/api/tasks/", json={
        "title": "Binary search implementation",
        "description": (
            "Write a Python function that implements binary search on a sorted list. "
            "Include edge cases: empty list, target not found, duplicate values. "
            "Add basic unit tests inside the same file using assert statements."
        ),
    })
    r.raise_for_status()
    task = r.json()
    task_id = task["id"]
    print(f"✓ Task created: {task_id}")

    # Poll
    terminal = {"awaiting_approval", "completed", "failed", "rejected"}
    while True:
        r = httpx.get(f"{BASE}/api/tasks/{task_id}")
        task = r.json()
        status = task["status"]
        print(f"  Status: {status}")
        if status in terminal:
            break
        time.sleep(3)

    if status == "awaiting_approval":
        print("\n🔍 Task is awaiting approval. Auto-approving...")
        r = httpx.post(f"{BASE}/api/tasks/{task_id}/approve", json={
            "action": "approve",
            "reviewer": "demo-script",
            "comment": "LGTM",
        })
        r.raise_for_status()
        print(f"✓ Approved: {r.json()}")

        # Wait for PR
        while True:
            r = httpx.get(f"{BASE}/api/tasks/{task_id}")
            task = r.json()
            status = task["status"]
            print(f"  Status: {status}")
            if status in {"completed", "failed"}:
                break
            time.sleep(3)

    print(f"\n{'✓' if status == 'completed' else '✗'} Final status: {status}")
    if task.get("pr_url"):
        print(f"  PR: {task['pr_url']}")
    if task.get("error"):
        print(f"  Error: {task['error']}")


if __name__ == "__main__":
    main()
