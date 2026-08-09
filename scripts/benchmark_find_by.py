import sys
from pathlib import Path
import time

# Ensure we can import paios and tests
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from paios.repositories.json_repositories import EventJsonRepository
from paios.repositories.json_store import JsonStore
from paios.domain.value_objects.identifiers import EventId, UserId
from paios.domain.enums import EventStatus
from tests.repositories.conftest import build_completed_event
from paios.repositories.serialization import serialize_event

class MockStore(JsonStore):
    def __init__(self):
        super().__init__("/tmp/dummy_data_dir")
    def read(self, filename):
        return []
    def write(self, filename, records):
        pass

def run_benchmark():
    store = MockStore()
    repo = EventJsonRepository(store)

    num_records = 2000
    print(f"Generating {num_records} detailed event records...")

    # We will build a realistic complete event, serialize it, and repeat it to build a large mock file
    sample_event_completed = build_completed_event("evt_comp")
    sample_event_archived = build_completed_event("evt_arch")
    sample_event_archived.transition_to(EventStatus.ARCHIVED, sample_event_archived.end_time)

    serialized_completed = serialize_event(sample_event_completed)
    serialized_archived = serialize_event(sample_event_archived)

    records = []
    for i in range(num_records):
        # alternate between completed and archived, and vary user_id slightly
        if i % 2 == 0:
            rec = dict(serialized_completed)
            rec["event_id"] = f"evt_{i:05d}"
            rec["user_id"] = "user_001" if i % 10 != 0 else "user_other"
        else:
            rec = dict(serialized_archived)
            rec["event_id"] = f"evt_{i:05d}"
            rec["user_id"] = "user_001"
        records.append(rec)

    # Mock _records to return this list
    repo._records = lambda: list(records)

    # Warm up
    for _ in range(5):
        repo.find_by(user_id=UserId("user_001"), status=EventStatus.ARCHIVED)

    print("\n[Scenario A] 1,000 records match (50% match rate)")
    start_time = time.perf_counter()
    iterations = 50
    for _ in range(iterations):
        results = repo.find_by(user_id=UserId("user_001"), status=EventStatus.ARCHIVED)
        assert len(results) == num_records // 2
    end_time = time.perf_counter()
    elapsed = end_time - start_time
    avg_time_ms = (elapsed / iterations) * 1000
    print(f"Total time: {elapsed:.6f} seconds")
    print(f"Average time per query: {avg_time_ms:.6f} ms")

    print("\n[Scenario B] Only 1 record matches (0.05% match rate)")
    # We will query for an event_id that only appears once
    start_time_b = time.perf_counter()
    iterations_b = 500
    for _ in range(iterations_b):
        results = repo.find_by(event_id=EventId("evt_00000"))
        assert len(results) == 1
    end_time_b = time.perf_counter()
    elapsed_b = end_time_b - start_time_b
    avg_time_ms_b = (elapsed_b / iterations_b) * 1000
    print(f"Total time: {elapsed_b:.6f} seconds")
    print(f"Average time per query: {avg_time_ms_b:.6f} ms")

if __name__ == "__main__":
    run_benchmark()
