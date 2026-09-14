"""
Pipeline unificado:
    1. Toma un CSV con direcciones.
    2. Geocodifica cada dirección con la API de Catastro Bogotá (IDECA) (lat, lon).
    3. Con esas coordenadas, busca a qué localidad de Bogotá pertenece,
       usando el shapefile oficial de localidades.
    4. Guarda un CSV final con: direccion, longitud, latitud, localidad.
"""
 
import time
import pandas as pd
import requests
import geopandas as gpd
from shapely.geometry import Point
 
 
# =========================================================
# CONFIGURACIÓN
# =========================================================
API_KEY = ""
BASE_URL = "https://catalogopmb.catastrobogota.gov.co/PMBWeb/web/api"
 
ARCHIVO_ENTRADA = ".csv"
ARCHIVO_SALIDA = ".csv"
COLUMNA_DIRECCION = "direccion"
 
SHAPEFILE_LOCALIDADES = "loca\Loca.shp" 
 
PAUSA_ENTRE_REQUESTS = 0.3  # segundos, para no saturar la API
# =========================================================
 
 
class LocalidadFinder:
    def __init__(self, shapefile_path: str, columna_nombre: str = None):
        self.gdf = gpd.read_file(shapefile_path)
 
        if self.gdf.crs is None:
            raise ValueError(
                "El shapefile no tiene un CRS definido. Verifica el archivo .prj."
            )
        if self.gdf.crs.to_epsg() != 4326:
            self.gdf = self.gdf.to_crs(epsg=4326)
 
        self.columna_nombre = columna_nombre or self._detectar_columna_nombre()
 
    def _detectar_columna_nombre(self) -> str:
        columna_localidad = "LocNombre1"

        if columna_localidad in self.gdf.columns:
            return columna_localidad
        else:
            raise ValueError(
                "No se pudo detectar automáticamente la columna con el nombre de la "
                f"localidad. Columnas disponibles: {list(self.gdf.columns)}. "
                "Especifica el parámetro 'columna_nombre' al crear LocalidadFinder."
            )
 
    def buscar(self, lat, lon):
        """Devuelve el nombre de la localidad, o None si lat/lon son inválidos."""
        if pd.isna(lat) or pd.isna(lon):
            return None
 
        punto = Point(lon, lat)  
        contiene = self.gdf[self.gdf.contains(punto)]
 
        if not contiene.empty:
            return contiene.iloc[0][self.columna_nombre]
 
        distancias = self.gdf.geometry.distance(punto)
        idx_mas_cercano = distancias.idxmin()
        return self.gdf.loc[idx_mas_cercano, self.columna_nombre]
 
 
def geocodificar_ideca(direccion, apikey=API_KEY, timeout=10):

    params = {
        "cmd": "geocodificar",
        "apikey": apikey,
        "query": direccion
    }
    try:
        resp = requests.get(BASE_URL, params=params, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
 
        if data.get("status") and data["response"].get("success"):
            info = data["response"]["data"]
            return float(info["latitude"]), float(info["longitude"])
    except requests.exceptions.RequestException as e:
        print(f"Error con '{direccion}': {e}")
 
    return None, None
 
 
def procesar_csv(
    archivo_entrada,
    archivo_salida,
    shapefile_localidades,
    columna_direccion=COLUMNA_DIRECCION,
    pausa=PAUSA_ENTRE_REQUESTS,
):
    df_entrada = pd.read_csv(archivo_entrada)
 
    finder = LocalidadFinder(shapefile_localidades)
 
    direcciones = []
    latitudes = []
    longitudes = []
    localidades = []
 
    total = len(df_entrada)
    for i, direccion in enumerate(df_entrada[columna_direccion]):
        print(f"[{i+1}/{total}] Geocodificando: {direccion}")
        lat, lon = geocodificar_ideca(str(direccion))
 
        localidad = finder.buscar(lat, lon)
 
        direcciones.append(direccion)
        latitudes.append(lat)
        longitudes.append(lon)
        localidades.append(localidad)
 
        time.sleep(pausa)
 
    df_salida = pd.DataFrame({
        columna_direccion: direcciones,
        "latitud": latitudes,
        "longitud": longitudes,
        "localidad": localidades,
    })
    df_salida.to_csv(archivo_salida, index=False, encoding="utf-8-sig")
 
    exitosos = df_salida["latitud"].notna().sum()
    con_localidad = df_salida["localidad"].notna().sum()
    print(f"\n✅ Geocodificadas: {exitosos}/{total} direcciones.")
    print(f"✅ Con localidad asignada: {con_localidad}/{total}.")
    print(f"Guardado en: {archivo_salida}")
    return df_salida
 
   
if __name__ == "__main__":
    procesar_csv(
        ARCHIVO_ENTRADA,
        ARCHIVO_SALIDA,
        SHAPEFILE_LOCALIDADES,
        columna_direccion=COLUMNA_DIRECCION,
        pausa=PAUSA_ENTRE_REQUESTS,
    )