import tempfile
import unittest
from pathlib import Path
from typing import cast

import pandas as pd
from supabase import Client

from refill_storage import delete_refill


class FakeQuery:
    def __init__(self, client: "FakeSupabase", action: str) -> None:
        self.client = client
        self.action = action
        self.refill_id: int | None = None

    def select(self, columns: str) -> "FakeQuery":
        if columns != "id":
            raise AssertionError(f"Unexpected selected columns: {columns}")
        return FakeQuery(self.client, "select")

    def delete(self) -> "FakeQuery":
        self.action = "delete"
        return self

    def eq(self, column: str, refill_id: int) -> "FakeQuery":
        if column != "id":
            raise AssertionError(f"Unexpected filter column: {column}")
        self.refill_id = refill_id
        return self

    def execute(self) -> "FakeResponse":
        assert self.refill_id is not None
        if self.action == "delete":
            if self.client.delete_records:
                self.client.refill_ids.discard(self.refill_id)
            return FakeResponse([])
        return FakeResponse(
            [{"id": self.refill_id}]
            if self.refill_id in self.client.refill_ids
            else []
        )


class FakeResponse:
    def __init__(self, data: list[dict[str, int]]) -> None:
        self.data = data


class FakeSupabase:
    def __init__(self, refill_ids: set[int], delete_records: bool = True) -> None:
        self.refill_ids = refill_ids
        self.delete_records = delete_records

    def table(self, table_name: str) -> FakeQuery:
        if table_name != "refills":
            raise AssertionError(f"Unexpected table: {table_name}")
        return FakeQuery(self, "select")


class DeleteRefillTests(unittest.TestCase):
    def test_deletes_local_record_and_keeps_other_records(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            refills_file = Path(directory) / "repostatges.csv"
            pd.DataFrame([
                {"id": 101, "data": "2026-10-01", "litres": 10},
                {"id": 202, "data": "2026-10-02", "litres": 20},
            ]).to_csv(refills_file, index=False)

            delete_refill(101, refills_file, None)

            saved_data = pd.read_csv(refills_file)
            self.assertEqual(saved_data["id"].tolist(), [202])

    def test_missing_local_record_fails_without_modifying_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            refills_file = Path(directory) / "repostatges.csv"
            pd.DataFrame([{"id": 202, "litres": 20}]).to_csv(refills_file, index=False)
            original_data = refills_file.read_bytes()

            with self.assertRaises(LookupError):
                delete_refill(101, refills_file, None)

            self.assertEqual(refills_file.read_bytes(), original_data)

    def test_deletes_supabase_record_and_verifies_it_is_gone(self) -> None:
        supabase = FakeSupabase({101, 202})

        delete_refill(101, Path("unused.csv"), cast(Client, supabase))

        self.assertEqual(supabase.refill_ids, {202})

    def test_missing_supabase_record_fails(self) -> None:
        supabase = FakeSupabase({202})

        with self.assertRaises(LookupError):
            delete_refill(101, Path("unused.csv"), cast(Client, supabase))

        self.assertEqual(supabase.refill_ids, {202})

    def test_supabase_delete_that_did_not_remove_record_fails(self) -> None:
        supabase = FakeSupabase({101}, delete_records=False)

        with self.assertRaises(RuntimeError):
            delete_refill(101, Path("unused.csv"), cast(Client, supabase))

        self.assertEqual(supabase.refill_ids, {101})


if __name__ == "__main__":
    unittest.main()
