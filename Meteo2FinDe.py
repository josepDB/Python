#12/11/2026 9:41
import streamlit as st
import pandas as pd
import plotly.express as px
import geopandas as gpd
import plotly.graph_objects as go

#import plotly.io as pio
#
#pio.renderers.default = "vscode"    #afegit per visualitzar des de Visual Studio Code

# Configuració de la pàgina
st.set_page_config(page_title="Dashboard Meteorològic XEMA", layout="wide")
st.title("🌦️ Anàlisi de Dades Meteorològiques de Catalunya (XEMA)")

# Nom del fitxer CSV (canvia'l si el teu fitxer té un altre nom)
FITXER_CSV = "./dat/Carto_XEMA.csv"  #modificat

@st.cache_data
def carregar_dades(ruta,tipus=""):
    # Llegim el CSV ignoran possibles línies finals incompletes
    df = pd.read_csv(ruta, on_bad_lines="skip", dtype=tipus)#, decimal=','
    
    # Eliminem files que no tinguin Estat o VALOR vàlid (per exemple, l'última fila tallada)
    #df = df.dropna(subset=["DATA_LECTURA", "CODI_ESTACIO", "CODI_VARIABLE", "VALOR", "Estat"]).copy()
    
    # Convertim DATA_LECTURA a format datetime
    df["DATA_DT"] = pd.to_datetime(df["DATA_LECTURA"], format="%d/%m/%Y", errors="coerce")
    df['MES'] = df['DATA_DT'].dt.to_period('M').astype(str)
  
    #df = df.dropna(subset=["DATA_DT"])
    
    # Convertim VALOR de text amb coma ("0,5") a número decimal (0.5)
    df["VALOR_NUM"] = (
        df["VALOR"]
        .astype(str)
        .str.replace(",", ".", regex=False)
        .pipe(pd.to_numeric, errors="coerce")
    )

            # Creem una etiqueta combinada "CODI - Primer NOM_ESTACIO"
    mapa_estacions = df.groupby("CODI_ESTACIO")["NOM_ESTACIO"].first().to_dict()
    df["ESTACIO_ETIQUETA"] = df["CODI_ESTACIO"].map(lambda c: f"{c} - {mapa_estacions.get(c, '')}")
    
    # Normalitzem el codi de variable (ex. "1.000" -> "1000") per evitar problemes de format
    #df["CODI_VARIABLE"] = df["CODI_VARIABLE"].astype(str).str.replace(".", "", regex=False)
    
    return df

try:
    df = carregar_dades(FITXER_CSV,{'CODI_VARIABLE':str, 'VALOR': float,'LATITUD': float, 'LONGITUD': float})
except FileNotFoundError:
    st.error(f"No s'ha trobat el fitxer '{FITXER_CSV}'. Posa'l a la mateixa carpeta que aquest script o puja'l aquí sota.")
    fitxer_pujat = st.file_uploader("Puja el fitxer CSV de Meteocat", type=["csv"])
    if fitxer_pujat is not None:
        df = carregar_dades(fitxer_pujat,{'CODI_VARIABLE':str, 'VALOR': float,'LATITUD': float, 'LONGITUD': float})
    else:
        st.stop()

#---------- generació pestanyes
st.title('Informes meteorològics')
tab1, tab2, tab3 = st.tabs(["Estadístiques bàsiques","Heatmap","Cartografía"])

with tab1:

    #---------- stmetrics
    col1, col2, col3 = st.columns(3)
    col1.metric(label='VERSIO', value=1.0)
    col2.metric(label='Observatoris', value=df["CODI_ESTACIO"].unique().size)
    col3.metric(label='Nº variables',value=4)

    # --- BARRA LATERAL DE FILTRES ---
    st.sidebar.header("Filtres de selecció")

    # 1. Filtre de Dates (mínima i màxima per defecte)
    data_min = df["DATA_DT"].min().date()
    data_max = df["DATA_DT"].max().date()

    data_inici = st.sidebar.date_input("Data inici", value=data_min, min_value=data_min, max_value=data_max)
    data_final = st.sidebar.date_input("Data final", value=data_max, min_value=data_min, max_value=data_max)

    # 2. Filtre CODI_ESTACIO (Tots per defecte, mostrant el primer NOM_ESTACIO associat)
    opcions_estacions = sorted(df["ESTACIO_ETIQUETA"].unique())
    estacions_seleccionades = st.sidebar.multiselect(
        "Estació meteorològica (Totes per defecte)",
        options=opcions_estacions,
        default=[]  # Buit vol dir totes seleccionades
    )

    # 3. Filtre Estat ("Totes" per defecte)
    opcions_prov = ["Totes"] + sorted(df["NOM_PROVINCIA"].dropna().unique())
    prov_seleccionada = st.sidebar.selectbox("Provincies", options=opcions_prov, index=0)

    # --- APLICACIÓ DELS FILTRES ---
    mask = (df["DATA_DT"].dt.date >= data_inici) & (df["DATA_DT"].dt.date <= data_final)

    if estacions_seleccionades:
        mask = mask & (df["ESTACIO_ETIQUETA"].isin(estacions_seleccionades))

    if prov_seleccionada != "Totes":
        mask = mask & (df["NOM_PROVINCIA"]==prov_seleccionada)

    df_filtrat = df[mask]

    if df_filtrat.empty:
        st.warning("No hi ha dades disponibles amb la combinació de filtres actual.")
        st.stop()
    else:
        st.dataframe(df)

    # --- GRÀFIC 1: LINEAL DE TEMPERATURA MITJANA AL LLARG DEL TEMPS ---
    st.subheader("1. Evolució de la Temperatura Mitjana Diària (°C)")
    df_temp = df_filtrat[df_filtrat["CODI_VARIABLE"] == "1.000" ].copy()

    if not df_temp.empty:
        # Si hi ha moltes estacions seleccionades, calculem la mitjana diària o mostrem per estació
        if len(df_temp["ESTACIO_ETIQUETA"].unique()) > 15:
            st.info("S'estan mostrant més de 15 estacions. Es representa la mitjana global diària i el rang (pots filtrar estacions concretes a l'esquerra).")
            df_temp_agg = df_temp.groupby("DATA_DT", as_index=False)["VALOR_NUM"].mean()
            fig_temp = px.line(
                df_temp_agg,
                x="DATA_DT",
                y="VALOR_NUM",
                markers=True,
                labels={"DATA_DT": "Data", "VALOR_NUM": "Temperatura mitjana global (°C)"},
                color_discrete_sequence=px.colors.qualitative.Set1
            )
        else:
            df_temp = df_temp.sort_values("DATA_DT")
            fig_temp = px.line(
                df_temp,
                x="DATA_DT",
                y="VALOR_NUM",
                color="ESTACIO_ETIQUETA",
                markers=True,
                labels={"DATA_DT": "Data", "VALOR_NUM": "Temperatura (°C)", "ESTACIO_ETIQUETA": "Estació"},
                color_discrete_sequence=px.colors.qualitative.Set1
            )
        st.plotly_chart(fig_temp, use_container_width=True)
    else:
        st.info("No hi ha registres de temperatura mitjana per a aquesta selecció.")

    
    # GRÀFIC 2: BARRES APILADES DE PRECIPITACIÓ ACUMULADA DIÀRIA
    st.subheader("2. Suma de Precipitació Acumulada Diària (mm)")
    if prov_seleccionada=='Totes':
        df_pluja = df_filtrat[(df_filtrat["CODI_VARIABLE"]=="1.300")].copy()
    else:
        df_pluja = df_filtrat[(df_filtrat["CODI_VARIABLE"]=="1.300") & (df_filtrat['NOM_PROVINCIA']==prov_seleccionada)].copy()

    if not df_pluja.empty:
        df_pluja = (
            df_pluja.groupby(['ESTACIO_ETIQUETA','MES'])['VALOR_NUM'].sum()
            .reset_index(name="Pluja_Mes")        
            .sort_values("Pluja_Mes")
        )
        fig_pluja = px.bar(
            df_pluja,
            x="MES",
            y="Pluja_Mes",
            color="ESTACIO_ETIQUETA",
            barmode="stack",
            labels={"MES": "Data", "Pluja_Mes": "Precipitació (mm)", "ESTACIO_ETIQUETA": "Estació"},
            color_discrete_sequence=px.colors.qualitative.Set2
        )
        #df_pluja = df_pluja.sort_values("DATA_DT")
        #fig_pluja = px.bar(
        #    df_pluja,
        #    x="DATA_DT",
        #    y="VALOR_NUM",
        #    color="ESTACIO_ETIQUETA",
        #    barmode="stack",
        #    labels={"DATA_DT": "Data", "VALOR_NUM": "Precipitació (mm)", "ESTACIO_ETIQUETA": "Estació"},
        #    color_discrete_sequence=px.colors.qualitative.Set2
        #)
        st.plotly_chart(fig_pluja, use_container_width=True)
    else:
        st.info("No hi ha registres de precipitació per a aquesta selecció.")

    # GRÀFIC 3: PASTÍS DEL TOTAL DE DIES DE VENT A CADA ESTACIÓ
    st.subheader("3. Total de dies amb registre de vent de mes de 15Km per estació")
    # Filtrem la variable de ratxa màxima de vent (codi 1514) amb valor > 0
    df_vent = df_filtrat[(df_filtrat["CODI_VARIABLE"] == "1.514") & (df_filtrat["VALOR_NUM"] > 15)].copy()

    if not df_vent.empty:
        dies_vent = (
            df_vent.groupby("ESTACIO_ETIQUETA")["DATA_DT"]
            .nunique()
            .reset_index(name="Total_Dies_Vent")
            .sort_values("Total_Dies_Vent", ascending=False)
        )
        fig_vent = px.pie(
            dies_vent,
            names="ESTACIO_ETIQUETA",
            values="Total_Dies_Vent",
            hole=0.3,
            labels={"ESTACIO_ETIQUETA": "Estació", "Total_Dies_Vent": "Dies de vent"},
            color_discrete_sequence=px.colors.qualitative.Set3
        )
        fig_vent.update_traces(textposition="inside", textinfo="value+label")
        st.plotly_chart(fig_vent, use_container_width=True)
    else:
        st.info("No hi ha registres de vent per a les estacions seleccionades (només algunes estacions tenen anemòmetre a 2m).")

# GRÀFIC 4: HEATMAP AMB TOTES LES DADES DE CADA ESTACIÓ
with tab2:
    # 2. Barra lateral amb filtres interactius
    st.sidebar.header("Configuració del Heatmap")

    # Selector de variable meteorològica
    variables = df['NOM_VARIABLE'].dropna().unique()
    variable_sel = st.sidebar.selectbox("Selecciona la variable:", variables)

    # Selector d'agrupació temporal
    agrupacio = st.sidebar.radio(
        "Resolució temporal:",
        options=["Diària", "Mitjana / Suma Mensual"],
        index=1
    )

    # Filtrar dades per la variable seleccionada
    df_var = df[df['NOM_VARIABLE'] == variable_sel].copy()
    unitat = df_var['UNITAT'].dropna().iloc[0] if not df_var['UNITAT'].dropna().empty else ""

    # Selector d'estacions (per defecte en mostrem 25 per facilitar la lectura)
    totes_estacions = sorted(df_var['NOM_ESTACIO'].dropna().unique())
    estacions_sel = st.sidebar.multiselect(
        "Filtra estacions (buida = totes):",
        options=totes_estacions,
        default=totes_estacions[:25]
    )

    if estacions_sel:
        df_var = df_var[df_var['NOM_ESTACIO'].isin(estacions_sel)]

    # 3. Creació de la matriu (taula dinàmica) per al Heatmap
    if agrupacio == "Diària":
        matriu = df_var.pivot_table(
            index='NOM_ESTACIO',
            columns='DATA_DT',
            values='VALOR',
            aggfunc='mean'
        )
        # Formatem les dates per a l'eix X
        matriu.columns = matriu.columns.strftime('%d/%m/%Y')
        etiqueta_x = "Data"
    else:
        # Si és precipitació acumulada, fem la suma mensual; per a la resta, la mitjana
        funcio_agregacio = 'sum' if 'Precipitació' in variable_sel else 'mean'
        matriu = df_var.pivot_table(
            index='NOM_ESTACIO',
            columns='MES',
            values='VALOR',
            aggfunc=funcio_agregacio
        )
        etiqueta_x = "Mes"

    # Ordenem alfabèticament les estacions
    matriu = matriu.sort_index()

    # 4. Selecció de la paleta de colors segons la variable
    if "Temperatura" in variable_sel:
        escala_colors = "RdYlBu_r"  # Blau (fred) a Vermell (calor)
    elif "Precipitació" in variable_sel:
        escala_colors = "Blues"     # Blanc a Blau intens
    else:
        escala_colors = "Viridis"   # Per al vent

    # 5. Generació del gràfic Heatmap amb Plotly
    fig = px.imshow(
        matriu,
        labels=dict(x=etiqueta_x, y="Estació Meteorològica", color=f"Valor ({unitat})"),
        x=matriu.columns,
        y=matriu.index,
        color_continuous_scale=escala_colors,
        aspect="auto"
    )

    # Ajustem l'alçada dinàmicament segons el nombre d'estacions mostrades
    alcada_grafic = max(500, len(matriu.index) * 22)
    fig.update_layout(
        title=f"{variable_sel} ({agrupacio})",
        height=alcada_grafic,
        xaxis_nticks=20
    )

    st.plotly_chart(fig, use_container_width=True)

    # 6. Opció per visualitzar la taula de dades subjacent
    with st.expander("Veure taula de dades del Heatmap"):
        st.dataframe(matriu.round(2))

with tab3:
    #df=pd.read_csv("./dat/Carto_XEMA.csv", sep=",")
    df_temp = df[df['CODI_VARIABLE'].isin(['1.000', '1.001'])].copy()
    df_geo = df_temp.groupby(['NOM_ESTACIO', 'LATITUD', 'LONGITUD'])['VALOR'].agg(
        t_min='min',
        t_med='mean'
    ).reset_index()

    fig_map = px.scatter_map(df_geo,
                            lat=df_geo.LATITUD,
                            lon=df_geo.LONGITUD,
                            hover_name="NOM_ESTACIO",
                            hover_data={
                                # 1. Ocultamos las coordenadas para que el cuadro no sea gigante
                                "LATITUD": False,
                                "LONGITUD": False,
                                # 2. Mostramos las temperaturas formateadas a 1 decimal
                                "t_min": ":.1f", 
                                "t_med": ":.1f"
                                },
                            width=800,   # Ancho de la ventana del mapa
                            height=800,  # Alto de la ventana del mapa
                            )
    
    fig_map.update_layout(
        hovermode='closest',
        margin={"r":0, "t":0, "l":0, "b":0},
        map=dict(
            bearing=0,
            center=go.layout.map.Center(
                lat=41.75,
                lon=2
            ),
            zoom=7.2,
            pitch=0,
        ))
    
    st.plotly_chart(fig_map)

