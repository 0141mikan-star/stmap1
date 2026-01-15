import streamlit as st
import requests
import pandas as pd
import pydeck as pdk
from datetime import datetime

# --- ページ設定 ---
st.set_page_config(page_title="日本全国 気温3D Map", layout="wide")
st.title("🇯🇵 日本主要都市の気温推移 3Dビジュアライゼーション")

# --- 1. 全国主要都市のデータ定義 ---
cities = {
    'Sapporo':   {'lat': 43.0618, 'lon': 141.3545},
    'Aomori':    {'lat': 40.8244, 'lon': 140.7400},
    'Sendai':    {'lat': 38.2682, 'lon': 140.8694},
    'Niigata':   {'lat': 37.9022, 'lon': 139.0236},
    'Tokyo':     {'lat': 35.6895, 'lon': 139.6917},
    'Kanazawa':  {'lat': 36.5613, 'lon': 136.6562},
    'Nagoya':    {'lat': 35.1815, 'lon': 136.9066},
    'Osaka':     {'lat': 34.6937, 'lon': 135.5023},
    'Hiroshima': {'lat': 34.3853, 'lon': 132.4553},
    'Kochi':     {'lat': 33.5588, 'lon': 133.5312},
    'Fukuoka':   {'lat': 33.5904, 'lon': 130.4017},
    'Kagoshima': {'lat': 31.5600, 'lon': 130.5580},
    'Naha':      {'lat': 26.2124, 'lon': 127.6809}
}

# --- 2. データ取得関数 (高速化: まとめて取得) ---
@st.cache_data(ttl=3600)  # 1時間キャッシュ
def fetch_forecast_data():
    lats = [coords['lat'] for coords in cities.values()]
    lons = [coords['lon'] for coords in cities.values()]
    city_names = list(cities.keys())

    # Open-Meteoはカンマ区切りで複数地点を一括取得可能
    BASE_URL = 'https://api.open-meteo.com/v1/forecast'
    params = {
        'latitude': lats,
        'longitude': lons,
        'hourly': 'temperature_2m',
        'timezone': 'Asia/Tokyo',
        'forecast_days': 1 # 今日1日分
    }
    
    try:
        response = requests.get(BASE_URL, params=params)
        response.raise_for_status()
        data = response.json()
        
        # 複数地点の場合、dataはリストで返ってくる
        all_records = []
        
        # レスポンスが1地点か複数地点かで構造が変わるための対応
        data_list = data if isinstance(data, list) else [data]

        for i, city_data in enumerate(data_list):
            city_name = city_names[i]
            times = city_data['hourly']['time']
            temps = city_data['hourly']['temperature_2m']
            
            for t, temp in zip(times, temps):
                all_records.append({
                    'City': city_name,
                    'lat': lats[i],
                    'lon': lons[i],
                    'Time': t, # ISO format string
                    'Temperature': temp
                })
                
        return pd.DataFrame(all_records)

    except Exception as e:
        st.error(f"データ取得エラー: {e}")
        return pd.DataFrame()

# --- 3. 色決定関数 (色合いを明るく・温度で変化) ---
def get_color(temp):
    # 透明度(Alpha)は180/255
    if temp < 0:
        return [0, 0, 255, 200]      # 氷点下: 青
    elif temp < 10:
        return [0, 255, 255, 200]    # 10度未満: シアン
    elif temp < 20:
        return [0, 255, 0, 200]      # 20度未満: 緑
    elif temp < 25:
        return [255, 165, 0, 200]    # 25度未満: オレンジ
    else:
        return [255, 0, 0, 200]      # 25度以上: 赤

# データ読み込み
with st.spinner('全国の気象データをロード中...'):
    full_df = fetch_forecast_data()

if not full_df.empty:
    # --- 4. タイムスライダー (アニメーション要素) ---
    # ユニークな時間リストを作成
    time_options = full_df['Time'].unique()
    
    # スライダーで選択 (デフォルトは今の時間に近いもの)
    current_hour_iso = datetime.now().strftime('%Y-%m-%dT%H:00')
    try:
        default_index = list(time_options).index(current_hour_iso)
    except ValueError:
        default_index = 0

    col_control, col_map = st.columns([1, 3])

    with col_control:
        st.subheader("🎮 コントロール")
        selected_time = st.select_slider(
            "時刻を選択してください",
            options=time_options,
            value=time_options[default_index]
        )
        
        st.info(f"選択中の時刻: **{selected_time}**")

        # 選択された時間でフィルタリング
        df_filtered = full_df[full_df['Time'] == selected_time].copy()

        # 高さ計算 (極端に短くならないようにオフセットを追加)
        # マイナス気温でも埋もれないように +20 してから倍率を掛ける工夫
        df_filtered['elevation'] = (df_filtered['Temperature'] + 20) * 2000
        
        # 色のカラムを追加
        df_filtered['color'] = df_filtered['Temperature'].apply(get_color)

        st.markdown("---")
        st.write("📊 **気温リスト**")
        st.dataframe(
            df_filtered[['City', 'Temperature']].sort_values('Temperature', ascending=False),
            use_container_width=True,
            hide_index=True
        )

    with col_map:
        # Pydeck 設定
        view_state = pdk.ViewState(
            latitude=36.0,      # 日本の中心付近
            longitude=138.0,
            zoom=4.5,           # 全国が見えるズーム率
            pitch=50,
            bearing=0
        )

        layer = pdk.Layer(
            "ColumnLayer",
            data=df_filtered,
            get_position='[lon, lat]',
            get_elevation='elevation',
            elevation_scale=1,
            radius=25000,          # 全国マップなので少し太く
            get_fill_color='color',# 計算した色を使用
            pickable=True,
            auto_highlight=True,
            extruded=True,
        )

        st.pydeck_chart(pdk.Deck(
            layers=[layer],
            initial_view_state=view_state,
            tooltip={
                "html": """
                    <div style='background: grey; padding: 10px; color: white; border-radius: 5px;'>
                        <b>{City}</b><br>
                        時刻: {Time}<br>
                        気温: <b>{Temperature}</b> °C
                    </div>
                """,
                "style": {"color": "white"}
            }
        ))
    
    st.caption("出典: Open-Meteo API | スライダーを動かすと時間帯ごとの気温変化を確認できます。")

else:
    st.error("データの取得に失敗しました。")
