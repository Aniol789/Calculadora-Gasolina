from pathlib import Path

import pandas as pd
from supabase import Client


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
