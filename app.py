from __future__ import annotations

import hmac
import json
from datetime import date
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError
from supabase import Client, create_client


st.set_page_config(page_title="Control de combustible", page_icon="⛽", layout="wide")

DATA_DIR = Path("data")
REFILLS_FILE = DATA_DIR / "repostatges.csv"
CARS_FILE = DATA_DIR / "cotxes.json"
REFILL_COLUMNS = [
    "id", "data", "cotxe", "quilometratge", "litres", "preu_litre", "cost_total", "diposit_ple", "notes",
]


@st.cache_resource
def create_supabase_client(url: str, key: str) -> Client:
    return create_client(url, key)


def get_supabase_client() -> Client | None:
    try:
        settings = st.secrets["supabase"]
    except (KeyError, StreamlitSecretNotFoundError):
        return None
    return create_supabase_client(settings["url"], settings["key"])


SUPABASE = get_supabase_client()


def require_app_access() -> None:
    if SUPABASE is None or st.session_state.get("authenticated"):
        return
    try:
        password = st.secrets["app"]["access_password"]
    except (KeyError, StreamlitSecretNotFoundError):
        st.error("Falta configurar la contrasenya d'accés als secrets de Streamlit.")
        st.stop()
    if not password:
        st.error("La contrasenya d'accés de l'aplicació no pot estar buida.")
        st.stop()

    st.title("⛽ Control de combustible")
    with st.form("app_login"):
        entered_password = st.text_input("Contrasenya d'accés", type="password")
        submitted = st.form_submit_button("Entra", type="primary", use_container_width=True)
    if submitted:
        if hmac.compare_digest(entered_password, password):
            st.session_state["authenticated"] = True
            st.rerun()
        st.error("La contrasenya no és correcta.")
    st.stop()


def initialise_storage() -> None:
    """Create local data files only on the first launch when Supabase is not configured."""
    if SUPABASE is not None:
        return
    DATA_DIR.mkdir(exist_ok=True)
    if not CARS_FILE.exists():
        CARS_FILE.write_text(json.dumps(["Cotxe 1", "Cotxe 2"], ensure_ascii=False), encoding="utf-8")
    if not REFILLS_FILE.exists():
        pd.DataFrame(columns=REFILL_COLUMNS).to_csv(REFILLS_FILE, index=False)


def load_cars() -> list[str]:
    if SUPABASE is not None:
        response = SUPABASE.table("cars").select("name").order("name").execute()
        return [row["name"] for row in response.data]
    return json.loads(CARS_FILE.read_text(encoding="utf-8"))


def save_cars(cars: list[str]) -> None:
    if SUPABASE is not None:
        SUPABASE.table("cars").upsert([{"name": car} for car in cars]).execute()
        return
    CARS_FILE.write_text(json.dumps(cars, ensure_ascii=False, indent=2), encoding="utf-8")


def load_refills() -> pd.DataFrame:
    if SUPABASE is not None:
        response = SUPABASE.table("refills").select("*").order("data").execute()
        data = pd.DataFrame(response.data, columns=REFILL_COLUMNS)
        if data.empty:
            return data
        data["data"] = pd.to_datetime(data["data"])
        for column in ["quilometratge", "litres", "preu_litre", "cost_total"]:
            data[column] = pd.to_numeric(data[column], errors="coerce")
        data["diposit_ple"] = data["diposit_ple"].astype(bool)
        return data
    data = pd.read_csv(REFILLS_FILE)
    if data.empty:
        return pd.DataFrame(columns=REFILL_COLUMNS)
    data["data"] = pd.to_datetime(data["data"])
    for column in ["quilometratge", "litres", "preu_litre", "cost_total"]:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    data["diposit_ple"] = data["diposit_ple"].astype(str).str.lower().eq("true")
    return data


def save_refills(data: pd.DataFrame) -> None:
    result = data.copy()
    result["data"] = pd.to_datetime(result["data"]).dt.strftime("%Y-%m-%d")
    if SUPABASE is not None:
        SUPABASE.table("refills").upsert(result.to_dict(orient="records")).execute()
        return
    result.to_csv(REFILLS_FILE, index=False)


def add_consumption(data: pd.DataFrame) -> pd.DataFrame:
    """Calculate L/100 km between two full-tank fuel stops for each car."""
    data = data.sort_values(["cotxe", "data", "quilometratge"]).copy()
    data["consum_l_100"] = pd.NA
    for _, group in data.groupby("cotxe"):
        previous_full_odometer: float | None = None
        for index, row in group.iterrows():
            if bool(row["diposit_ple"]):
                if previous_full_odometer is not None and row["quilometratge"] > previous_full_odometer:
                    distance = row["quilometratge"] - previous_full_odometer
                    data.loc[index, "consum_l_100"] = row["litres"] / distance * 100
                previous_full_odometer = row["quilometratge"]
    return data


def euro(value: float) -> str:
    return f"{value:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


require_app_access()
initialise_storage()
if SUPABASE is None:
    st.warning(
        "Les dades es desen en fitxers locals. Perquè persisteixin a Streamlit Cloud, "
        "configura Supabase seguint les instruccions del README."
    )
st.markdown(
    """<style>
    .block-container {max-width: 950px; padding-top: 1.3rem; padding-bottom: 3rem;}
    [data-testid="stMetric"] {background: #f3f8f5; border-radius: 12px; padding: .6rem;}
    @media (max-width: 600px) {.block-container {padding-left: .8rem; padding-right: .8rem;} }
    </style>""",
    unsafe_allow_html=True,
)

cars = load_cars()
with st.sidebar:
    st.header("Els meus cotxes")
    new_car = st.text_input("Afegeix un cotxe", placeholder="Ex.: Seat Ibiza")
    if st.button("Desa el cotxe", use_container_width=True) and new_car.strip():
        if new_car.strip() not in cars:
            save_cars([*cars, new_car.strip()])
            st.rerun()
        st.warning("Aquest nom ja existeix.")
    st.caption("Pots començar canviant ‘Cotxe 1’ i ‘Cotxe 2’ per noms teus afegint els noms nous.")

st.title("⛽ Control de combustible")
st.caption(
    "Les dades es desen al núvol amb Supabase."
    if SUPABASE is not None
    else "Una llibreta de repostatges senzilla, guardada al teu dispositiu."
)

tab_add, tab_summary, tab_history = st.tabs(["➕ Nou repostatge", "📊 Resum", "🧾 Historial"])

with tab_add:
    st.subheader("Registra un repostatge")
    with st.form("new_refill", clear_on_submit=True):
        car = st.selectbox("Cotxe", cars)
        first, second = st.columns(2)
        with first:
            refill_date = st.date_input("Data", value=date.today(), format="DD/MM/YYYY")
            litres = st.number_input("Litres", min_value=0.01, step=0.01, format="%.2f")
        with second:
            odometer = st.number_input("Quilometratge (km)", min_value=0, step=1)
            price_per_litre = st.number_input("Preu per litre (€)", min_value=0.001, step=0.001, format="%.3f")
        full_tank = st.checkbox("He omplert el dipòsit", value=True, help="Necessari per calcular correctament el consum.")
        notes = st.text_input("Notes (opcional)", placeholder="Ex.: viatge a Girona")
        total = litres * price_per_litre
        st.info(f"Cost calculat: **{euro(total)}**")
        submitted = st.form_submit_button("Desa el repostatge", type="primary", use_container_width=True)
    if submitted:
        data = load_refills()
        duplicate = (data["cotxe"].eq(car) & data["quilometratge"].eq(odometer)).any() if not data.empty else False
        if duplicate:
            st.error("Ja hi ha un repostatge d’aquest cotxe amb aquest quilometratge.")
        else:
            new_row = pd.DataFrame([{
                "id": pd.Timestamp.now().value, "data": refill_date, "cotxe": car,
                "quilometratge": odometer, "litres": litres, "preu_litre": price_per_litre,
                "cost_total": total, "diposit_ple": full_tank, "notes": notes,
            }])
            save_refills(pd.concat([data, new_row], ignore_index=True))
            st.success("Repostatge desat correctament.")

with tab_summary:
    data = add_consumption(load_refills())
    if data.empty:
        st.info("Encara no hi ha repostatges. Afegeix-ne un a la pestanya anterior.")
    else:
        filters, year_column = st.columns(2)
        with filters:
            selected_car = st.selectbox("Cotxe a analitzar", ["Tots"] + cars, key="summary_car")
        with year_column:
            available_years = sorted(data["data"].dt.year.dropna().unique(), reverse=True)
            selected_year = st.selectbox("Any", ["Tots"] + available_years)
        filtered = data.copy()
        if selected_car != "Tots":
            filtered = filtered[filtered["cotxe"] == selected_car]
        if selected_year != "Tots":
            filtered = filtered[filtered["data"].dt.year == selected_year]
        total_litres = filtered["litres"].sum()
        total_cost = filtered["cost_total"].sum()
        avg_consumption = filtered["consum_l_100"].dropna().mean()
        c1, c2, c3 = st.columns(3)
        c1.metric("Litres", f"{total_litres:.1f} L")
        c2.metric("Despesa", euro(total_cost))
        c3.metric("Consum mitjà", f"{avg_consumption:.2f} L/100 km" if pd.notna(avg_consumption) else "Encara no disponible")
        if not filtered.empty:
            st.subheader("Despesa mensual")
            monthly = filtered.assign(mes=filtered["data"].dt.strftime("%Y-%m")).groupby("mes", as_index=False)["cost_total"].sum()
            st.altair_chart(alt.Chart(monthly).mark_bar(color="#16794a").encode(
                x=alt.X("mes:N", title="Mes"), y=alt.Y("cost_total:Q", title="Euros"), tooltip=["mes", "cost_total"]
            ), use_container_width=True)
            consumption = filtered.dropna(subset=["consum_l_100"])
            if not consumption.empty:
                st.subheader("Evolució del consum")
                st.altair_chart(alt.Chart(consumption).mark_line(point=True, color="#e07a25").encode(
                    x=alt.X("data:T", title="Data"), y=alt.Y("consum_l_100:Q", title="L/100 km"),
                    tooltip=["data", "cotxe", "consum_l_100"]
                ), use_container_width=True)

with tab_history:
    data = add_consumption(load_refills())
    if data.empty:
        st.info("No hi ha dades per mostrar.")
    else:
        view = data.sort_values("data", ascending=False).copy()
        view["data"] = view["data"].dt.strftime("%d/%m/%Y")
        view["consum_l_100"] = view["consum_l_100"].round(2)
        st.dataframe(view[["data", "cotxe", "quilometratge", "litres", "preu_litre", "cost_total", "consum_l_100", "notes"]],
                     use_container_width=True, hide_index=True,
                     column_config={"data": "Data", "cotxe": "Cotxe", "quilometratge": "Km", "litres": "Litres", "preu_litre": "€/L", "cost_total": st.column_config.NumberColumn("Cost", format="%.2f €"), "consum_l_100": st.column_config.NumberColumn("L/100 km", format="%.2f"), "notes": "Notes"})
        st.download_button("Descarrega les dades (CSV)", data.drop(columns=["consum_l_100"]).to_csv(index=False).encode("utf-8"), "repostatges.csv", "text/csv", use_container_width=True)
