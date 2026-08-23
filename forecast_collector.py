import os
import requests
import pandas as pd
from datetime import datetime, timedelta
from config import TARGET_LOCATIONS, SERVICE_KEY, SKY_MAP, PTY_MAP, LATEST_DIR

API_BASE_URL = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getUltraSrtFcst"
BASE_DIR = "weather_forecast_data" 

def get_recent_ultrasrt_base_time():
    """
    초단기예보(UltraSrtFcst)는 매시 30분에 발표됩니다.
    현재 시각을 기준으로 API가 정상 응답을 주는 가장 최근의 발표 일자와 시각(HH30)을 계산합니다.
    """
    now = datetime.now()
    hour = now.hour
    minute = now.minute
    
    # 현재 분이 30분 미만이면, 아직 이번 시간 30분 발표가 안 되었으므로 1시간 전의 30분이 최신입니다.
    if minute < 30:
        target_time = now - timedelta(hours=1)
        base_date_str = target_time.strftime('%Y%m%d')
        base_time_str = f"{target_time.hour:02d}30"
    else:
        # 30분이 넘었으면 현재 시간의 30분이 최신 발표입니다.
        base_date_str = now.strftime('%Y%m%d')
        base_time_str = f"{hour:02d}30"
        
    return base_date_str, base_time_str

def fetch_and_save_weather_data():
    now = datetime.now()
    
    # 고정값 대신 동적으로 가장 최근 발표 시각 계산
    base_date_str, base_time_str = get_recent_ultrasrt_base_time()
    year_month_str = now.strftime('%Y%m')  # 월별 분리용 (예: '202608')
    
    # 최신 데이터용 디렉터리 미리 생성
    os.makedirs(LATEST_DIR, exist_ok=True)
    
    print(f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] 🔍 주요 지역 기상청 초단기예보 수집 시작 (Base: {base_date_str} {base_time_str})...\n")

    for loc in TARGET_LOCATIONS:
        loc_name = loc["name"]
        nx = loc["nx"]
        ny = loc["ny"]
        
        # 1. 월별 누적용 하위 폴더 및 파일 경로
        monthly_dir_path = os.path.join(BASE_DIR, f"{loc_name}_{nx}_{ny}")
        os.makedirs(monthly_dir_path, exist_ok=True)
        monthly_csv = os.path.join(monthly_dir_path, f"{loc_name}_{nx}_{ny}_{year_month_str}_forecast.csv")
        
        # 2. 최신 데이터 1줄용 파일 경로
        latest_csv = os.path.join(LATEST_DIR, f"{loc_name}_{nx}_{ny}_forecast_latest.csv")
        
        full_url = f"{API_BASE_URL}?serviceKey={SERVICE_KEY}&pageNo=1&numOfRows=1000&dataType=JSON&base_date={base_date_str}&base_time={base_time_str}&nx={nx}&ny={ny}"
        
        print(f"📍 [{loc_name} (NX:{nx}, NY:{ny})] 날씨 예보 조회 중...")
        
        try:
            response = requests.get(full_url)
            response.raise_for_status()
            data = response.json()
            
            if data["response"]["header"]["resultCode"] != "00":
                print(f"❌ [{loc_name}] API 에러 발생: {data['response']['header']['resultMsg']}\n")
                continue
                
            items = data["response"]["body"]["items"]["item"]
            df = pd.DataFrame(items)
            
            pivot_df = df.pivot(index=["fcstDate", "fcstTime"], columns="category", values="fcstValue").reset_index()
            pivot_df.columns.name = None
            
            row_data = {
                "수집시각": now.strftime("%Y-%m-%d %H:%M:%S"),
                "발표일자": df["baseDate"].iloc[0],
                "발표시각": df["baseTime"].iloc[0],
                "격자X": nx,
                "격자Y": ny
            }
            
            fcst_times = sorted(pivot_df["fcstTime"].unique())
            for idx, t in enumerate(fcst_times, start=1):
                sub = pivot_df[pivot_df["fcstTime"] == t].iloc[0]
                row_data[f"+{idx}_예보시각"] = t
                row_data[f"+{idx}_기온(℃)[T1H]"] = sub.get("T1H")
                row_data[f"+{idx}_습도(%)[REH]"] = sub.get("REH")
                row_data[f"+{idx}_강수확률(%)[POP]"] = sub.get("POP")
                row_data[f"+{idx}_강수형태[PTY]"] = PTY_MAP.get(str(sub.get("PTY")), "기타")
                row_data[f"+{idx}_1시간강수량[RN1]"] = sub.get("RN1")
                row_data[f"+{idx}_하늘상태[SKY]"] = SKY_MAP.get(str(sub.get("SKY")), "기타")
                row_data[f"+{idx}_풍속(m/s)[WSD]"] = sub.get("WSD")
                row_data[f"+{idx}_풍향(deg)[VEC]"] = sub.get("VEC")
            
            result_df = pd.DataFrame([row_data])
            
            # --- A. 월별 CSV 파일 누적 저장 (Append) ---
            file_exists = os.path.exists(monthly_csv)
            file_empty = file_exists and os.path.getsize(monthly_csv) == 0

            if not file_exists or file_empty:
                result_df.to_csv(monthly_csv, index=False, encoding='utf-8-sig')
                print(f"✅ [{loc_name}] 월별 누적 파일 생성: {monthly_csv}")
            else:
                result_df.to_csv(monthly_csv, mode='a', index=False, header=False, encoding='utf-8-sig')
                print(f"✅ [{loc_name}] 월별 누적 데이터 추가 완료")
                
            # --- B. 최신 예보 데이터 1줄 파일 갱신 (Overwrite) ---
            result_df.to_csv(latest_csv, index=False, encoding='utf-8-sig')
            print(f"✨ [{loc_name}] 최신 예보 1줄 파일 갱신 완료: {latest_csv}")
                
        except Exception as e:
            print(f"❌ [{loc_name}] 예외 발생: {e}")
            
        print("-" * 40)

if __name__ == "__main__":
    fetch_and_save_weather_data()