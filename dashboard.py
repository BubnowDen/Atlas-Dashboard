import csv
import io
import pandas as pd
import plotly.express as px
import requests
import streamlit as st

st.set_page_config(
    page_title="Авиапарк: Zeus & Athena", page_icon="✈️", layout="wide"
)

# --- НАСТРОЙКИ GOOGLE ТАБЛИЦЫ ---
SHEET_ID = "1dUeFz-oEDqHxo4mqLSjEyP2wXMI2Yc4pZ8U9aCnPXBw"
# Экспортируем лист Total (gid=0 — первый лист в таблице)
GSHEETS_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0"


# --- ЗАГРУЗКА И ПАРСИНГ ДАННЫХ ---
@st.cache_data(ttl=60)
def load_and_parse_data():
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(GSHEETS_URL, headers=headers)
    response.raise_for_status()
    csv_text = response.text

    # Проверка: если Google вернул HTML-страницу логина вместо CSV
    if "<html" in csv_text.lower() or "google-signin" in csv_text.lower():
        raise PermissionError(
            "Google Таблица вернула страницу авторизации. "
            "Откройте таблицу -> 'Поделиться' -> выберите 'Все, у кого есть ссылка' (Читатель)."
        )

    reader = csv.reader(io.StringIO(csv_text))
    rows = [[cell.strip() for cell in r] for r in reader]

    # Находим индексы строк со словом Zeus (их ровно 2: для моделей и для семейств)
    zeus_indices = []
    mfg_row_idx = None
    all_planes = 0
    all_routes = 0

    for i, r in enumerate(rows):
        if any(cell.lower() == "zeus" for cell in r[:2]):
            zeus_indices.append(i)
        elif len(r) > 0 and r[0].lower() == "manufacturer":
            mfg_row_idx = i

        # Поиск счетчиков ALL Plane и All Route
        for j, cell in enumerate(r):
            clean_cell = cell.lower().replace(" ", "")
            if clean_cell == "allplane" and j + 1 < len(r):
                try:
                    all_planes = int(
                        r[j + 1].replace(" ", "").replace(",", "")
                    )
                except ValueError:
                    pass
            elif clean_cell == "allroute" and j + 1 < len(r):
                try:
                    all_routes = int(
                        r[j + 1].replace(" ", "").replace(",", "")
                    )
                except ValueError:
                    pass

    if len(zeus_indices) < 2:
        raise ValueError(
            f"Не удалось распознать структуру таблицы. Найдено блоков Zeus: {len(zeus_indices)} (ожидалось минимум 2)."
        )

    # 1. Первый блок Zeus — детальные модификации (заголовки идут строкой выше)
    m_idx = zeus_indices[0]
    models_row = rows[m_idx - 1]
    zeus_row = rows[m_idx]
    athena_row = rows[m_idx + 1]

    models_list = []
    for j in range(1, len(models_row)):
        m_name = models_row[j]
        if not m_name:
            continue
        z_cnt = (
            int(zeus_row[j])
            if j < len(zeus_row) and zeus_row[j].isdigit()
            else 0
        )
        a_cnt = (
            int(athena_row[j])
            if j < len(athena_row) and athena_row[j].isdigit()
            else 0
        )

        models_list.append(
            {"Model": m_name, "Alliance": "Zeus", "Count": z_cnt}
        )
        models_list.append(
            {"Model": m_name, "Alliance": "Athena", "Count": a_cnt}
        )
    df_models = pd.DataFrame(models_list)

    # 2. Второй блок Zeus — семейства
    f_idx = zeus_indices[1]
    fam_row = rows[f_idx - 1]
    zeus_fam_row = rows[f_idx]
    athena_fam_row = rows[f_idx + 1]

    fam_list = []
    for j in range(1, len(fam_row)):
        f_name = fam_row[j]
        if not f_name:
            continue
        z_cnt = (
            int(zeus_fam_row[j])
            if j < len(zeus_fam_row) and zeus_fam_row[j].isdigit()
            else 0
        )
        a_cnt = (
            int(athena_fam_row[j])
            if j < len(athena_fam_row) and athena_fam_row[j].isdigit()
            else 0
        )

        fam_list.append({"Family": f_name, "Alliance": "Zeus", "Count": z_cnt})
        fam_list.append(
            {"Family": f_name, "Alliance": "Athena", "Count": a_cnt}
        )
    df_families = pd.DataFrame(fam_list)

    # 3. Производители
    mfg_list = []
    if mfg_row_idx is not None:
        for r in rows[mfg_row_idx + 1 :]:
            if len(r) >= 2 and r[0] and r[1].isdigit():
                mfg_list.append({"Manufacturer": r[0], "Count": int(r[1])})
    df_mfg = pd.DataFrame(mfg_list)

    return df_models, df_families, df_mfg, all_planes, all_routes


# --- САЙДБАР ---
st.sidebar.title("Параметры")
if st.sidebar.button("🔄 Обновить данные из таблицы"):
    st.cache_data.clear()
    st.rerun()

# Загружаем данные с обработкой понятных ошибок
try:
    df_models, df_families, df_mfg, total_planes, total_routes = (
        load_and_parse_data()
    )
except PermissionError as pe:
    st.error(f"🔒 {pe}")
    st.stop()
except Exception as e:
    st.error(f"❌ Ошибка загрузки: {e}")
    st.stop()

# Расчет итогов
zeus_total = df_families[df_families["Alliance"] == "Zeus"]["Count"].sum()
athena_total = df_families[df_families["Alliance"] == "Athena"]["Count"].sum()
if total_planes == 0:
    total_planes = zeus_total + athena_total

# --- ШАПКА ДАШБОРДА (KPI) ---
st.title("✈️ Флот альянсов Zeus & Athena")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Всего самолетов", f"{total_planes:,}".replace(",", " "))
col2.metric(
    "Флот Zeus",
    f"{zeus_total:,}".replace(",", " "),
    f"{(zeus_total/total_planes)*100:.1f}%",
)
col3.metric(
    "Флот Athena",
    f"{athena_total:,}".replace(",", " "),
    f"{(athena_total/total_planes)*100:.1f}%",
)
col4.metric("Всего маршрутов", f"{total_routes:,}".replace(",", " "))

st.divider()

# --- ВКЛАДКИ ---
tab1, tab2, tab3 = st.tabs(
    [
        "🏭 Производители",
        "🗂️ Семейства самолетов",
        "🔍 Модели подробно",
    ]
)

# ВКЛАДКА 1: Производители
with tab1:
    col_left, col_right = st.columns(2)

    with col_left:
        fig_mfg = px.pie(
            df_mfg,
            names="Manufacturer",
            values="Count",
            title="Доля производителей в альянсах",
            hole=0.45,
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        fig_mfg.update_traces(textposition="inside", textinfo="percent+label")
        st.plotly_chart(fig_mfg, use_container_width=True)

    with col_right:
        alliance_summary = pd.DataFrame(
            {
                "Alliance": ["Zeus", "Athena"],
                "Count": [zeus_total, athena_total],
            }
        )
        fig_alliance = px.pie(
            alliance_summary,
            names="Alliance",
            values="Count",
            title="Распределение флота между Zeus и Athena",
            hole=0.45,
            color="Alliance",
            color_discrete_map={"Zeus": "#1f77b4", "Athena": "#ff7f0e"},
        )
        fig_alliance.update_traces(
            textposition="inside", textinfo="percent+value"
        )
        st.plotly_chart(fig_alliance, width='stretch')

    st.subheader("Количество самолетов по брендам")
    fig_bar_mfg = px.bar(
        df_mfg.sort_values(by="Count", ascending=False),
        x="Manufacturer",
        y="Count",
        text="Count",
        color="Manufacturer",
    )
    fig_bar_mfg.update_traces(textposition="outside")
    st.plotly_chart(fig_bar_mfg, width='stretch')

# ВКЛАДКА 2: Семейства
with tab2:
    st.subheader("Сравнение флота по семействам (Zeus vs Athena)")

    fam_order = (
        df_families.groupby("Family")["Count"]
        .sum()
        .sort_values(ascending=False)
        .index.tolist()
    )

    fig_fam = px.bar(
        df_families,
        x="Family",
        y="Count",
        color="Alliance",
        barmode="group",
        category_orders={"Family": fam_order},
        color_discrete_map={"Zeus": "#1f77b4", "Athena": "#ff7f0e"},
        title="Количество бортов каждого семейства",
    )
    fig_fam.update_layout(xaxis_tickangle=-45)
    st.plotly_chart(fig_fam, width='stretch')

    top5_fam = (
        df_families.groupby("Family")["Count"].sum().nlargest(5).reset_index()
    )
    st.info(
        "🏆 **Топ-5 самых массовых семейств:** "
        + ", ".join(
            [f"{r['Family']} ({r['Count']:,} шт.)" for _, r in top5_fam.iterrows()]
        )
    )

# ВКЛАДКА 3: Детальные модификации
with tab3:
    st.subheader("Детальная статистика по модификациям")

    c1, c2 = st.columns([1, 2])
    with c1:
        selected_alliance = st.selectbox(
            "Фильтр по альянсу:", ["Все", "Zeus", "Athena"]
        )
    with c2:
        top_n = st.slider("Показать Топ моделей:", 5, 50, 15)

    df_filtered = df_models.copy()
    if selected_alliance != "Все":
        df_filtered = df_filtered[df_filtered["Alliance"] == selected_alliance]

    top_models = (
        df_filtered.groupby("Model")["Count"]
        .sum()
        .nlargest(top_n)
        .reset_index()
    )

    fig_models = px.bar(
        top_models,
        x="Model",
        y="Count",
        text="Count",
        color="Count",
        color_continuous_scale="Teal",
        title=f"Топ-{top_n} модификаций ({selected_alliance})",
    )
    fig_models.update_traces(textposition="outside")
    fig_models.update_layout(xaxis_tickangle=-45)
    st.plotly_chart(fig_models, width='stretch')

    with st.expander("📄 Посмотреть полную сводную таблицу модификаций"):
        pivot_models = df_models.pivot(
            index="Model", columns="Alliance", values="Count"
        ).fillna(0)
        pivot_models["TOTAL"] = pivot_models["Zeus"] + pivot_models["Athena"]
        pivot_models = pivot_models.sort_values(by="TOTAL", ascending=False)
        st.dataframe(pivot_models, width='stretch')