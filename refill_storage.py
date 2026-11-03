from pathlib import Path

import pandas as pd
from supabase import Client


def latest_odometer(data: pd.DataFrame, car: str) -> int:
    car_refills = data.loc[data["cotxe"].eq(car)]
    return int(car_refills["quilometratge"].max()) if not car_refills.empty else 0


def add_refill_distances(data: pd.DataFrame) -> pd.DataFrame:
    result = data.sort_values(["cotxe", "data", "quilometratge"]).copy()
    result["km_des_de_repostatge"] = result.groupby("cotxe")["quilometratge"].diff()
    result.loc[result["km_des_de_repostatge"] < 0, "km_des_de_repostatge"] = float("nan")
    return result


def delete_refill(refill_id: int, refills_file: Path, supabase: Client | None) -> None:
    if supabase is not None:
        table = supabase.table("refills")
        existing = table.select("id").eq("id", refill_id).execute()
        if not existing.data:
            raise LookupError(f"No s’ha trobat el repostatge {refill_id}.")

        table.delete().eq("id", refill_id).execute()

        remaining = table.select("id").eq("id", refill_id).execute()
        if remaining.data:
            raise RuntimeError(
                f"El repostatge {refill_id} encara consta a Supabase després d’eliminar-lo."
            )
        return

    data = pd.read_csv(refills_file)
    if "id" not in data.columns:
        raise ValueError("El fitxer de repostatges no conté la columna d’identificador.")

    matching = pd.to_numeric(data["id"], errors="coerce").eq(refill_id)
    if not matching.any():
        raise LookupError(f"No s’ha trobat el repostatge {refill_id}.")

    data.loc[~matching].to_csv(refills_file, index=False)
    saved_data = pd.read_csv(refills_file)
    still_exists = pd.to_numeric(saved_data["id"], errors="coerce").eq(refill_id).any()
    if still_exists:
        raise RuntimeError(
            f"El repostatge {refill_id} encara consta al fitxer després d’eliminar-lo."
        )
