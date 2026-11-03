import tempfile
import unittest
from pathlib import Path
from typing import cast

import pandas as pd
from supabase import Client

from refill_storage import add_refill_distances, delete_refill, latest_odometer


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


class RefillDistanceTests(unittest.TestCase):
    def test_distance_is_calculated_per_car_from_odometer_readings(self) -> None:
        refills = pd.DataFrame([
            {"data": "2026-10-01", "cotxe": "Cotxe 1", "quilometratge": 10000},
            {"data": "2026-10-03", "cotxe": "Cotxe 2", "quilometratge": 5000},
            {"data": "2026-10-08", "cotxe": "Cotxe 1", "quilometratge": 10500},
            {"data": "2026-10-10", "cotxe": "Cotxe 2", "quilometratge": 5400},
        ])

        result = add_refill_distances(refills)
        distances = result.set_index(["cotxe", "quilometratge"])["km_des_de_repostatge"]

        self.assertTrue(pd.isna(distances.loc[("Cotxe 1", 10000)]))
        self.assertEqual(distances.loc[("Cotxe 1", 10500)], 500)
        self.assertTrue(pd.isna(distances.loc[("Cotxe 2", 5000)]))
        self.assertEqual(distances.loc[("Cotxe 2", 5400)], 400)

    def test_latest_odometer_is_car_specific_and_empty_car_starts_at_zero(self) -> None:
        refills = pd.DataFrame([
            {"cotxe": "Cotxe 1", "quilometratge": 10500},
            {"cotxe": "Cotxe 2", "quilometratge": 5400},
            {"cotxe": "Cotxe 1", "quilometratge": 10000},
        ])

        self.assertEqual(latest_odometer(refills, "Cotxe 1"), 10500)
        self.assertEqual(latest_odometer(refills, "Cotxe 2"), 5400)
        self.assertEqual(latest_odometer(refills, "Cotxe 3"), 0)


if __name__ == "__main__":
    unittest.main()
