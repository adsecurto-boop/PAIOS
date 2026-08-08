import sys
from pathlib import Path
import time

# Ensure we can import paios
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from paios.repositories.json_repositories import EventJsonRepository
from paios.repositories.json_store import JsonStore
from paios.domain.value_objects.identifiers import EventId

class MockStore(JsonStore):
    def __init__(self):
        super().__init__("/tmp/dummy_data_dir")
    def read(self, filename):
        return []
    def write(self, filename, records):
        pass

def run_benchmark():
    # Mock EventJsonRepository._serialize at the class level
    EventJsonRepository._serialize = staticmethod(
        lambda e: {"event_id": str(e.event_id), "description": "dummy"}
    )

    store = MockStore()
    repo = EventJsonRepository(store)

    # Create N dummy records
    num_records = 20000
    print(f"Generating {num_records} dummy records...")
    records = [{"event_id": f"evt_{i}", "description": "dummy"} for i in range(num_records)]

    # Mock _records to return this list
    repo._records = lambda: list(records)  # Copy list to mimic original read behavior structure
    repo._write = lambda recs: None

    # Dummy event to save (not duplicate)
    class DummyEvent:
        def __init__(self, event_id):
            self.event_id = EventId(event_id)

    event_to_save = DummyEvent("evt_new")

    # Warm up
    for _ in range(10):
        repo.save(event_to_save)

    print("Running benchmark...")
    start_time = time.perf_counter()
    iterations = 200
    for _ in range(iterations):
        repo.save(event_to_save)
    end_time = time.perf_counter()

    elapsed = end_time - start_time
    avg_time_ms = (elapsed / iterations) * 1000
    print(f"Total time for {iterations} saves with {num_records} records: {elapsed:.6f} seconds")
    print(f"Average time per save: {avg_time_ms:.6f} ms")

if __name__ == "__main__":
    run_benchmark()
