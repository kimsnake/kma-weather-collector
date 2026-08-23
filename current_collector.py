import os
import requests
import pandas as pd
from datetime import datetime, timedelta
from config import TARGET_LOCATIONS, SERVICE_KEY, SKY_MAP, PTY_MAP, LATEST_DIR

# 기상청 초단기실황(UltraSrtNcst - 현재 날씨) 조회 API 엔드포인트 URL
API_BASE_URL = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getUltraSrtNcst"
BASE_DIR = "weather_current_data" 

def fetch_and_save_current_weather():
    """
    지정된 주요 지역들의 기상청 초단기실황(현재 날씨 관측값) 데이터를 조회하여,
    월별 누적 CSV 파일과 최신 상태 1줄 덮어쓰기 CSV 파일로 각각 저장하는 함수
    """
    now = datetime.now()
    
    # 초단기실황은 매시 정각에 발표되며, 기상청 시스템상 보통 40분~50분이 지나야 데이터가 안정적으로 제공됩니다.
    # 따라서 안전하게 현재 시각 기준으로 1시간 전 시각을 타겟으로 잡습니다.
    target_time = now - timedelta(hours=1)
    base_date_str = target_time.strftime('%Y%m%d')  # 기준 날짜 (YYYYMMDD 형식)
    base_time_str = target_time.strftime('%H00')    # 기준 시각 정각 (예: '2200')
    
    year_month_str = now.strftime('%Y%m')           # 월별 파일 분리를 위한 연월 문자열 (예: '202608')
    
    # 최신 실황 데이터(.csv)들을 모아둘 공용 디렉터리가 없다면 미리 생성
    os.makedirs(LATEST_DIR, exist_ok=True)
    
    print(f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] 🔍 주요 지역 기상청 초단기실황(현재 날씨) 수집 시작...\n")

    # config.py에서 불러온 대상 지역 리스트(서울_대치동, 성남, 익산, 전주 등)를 순회하며 데이터 수집
    for loc in TARGET_LOCATIONS:
        loc_name = loc["name"]
        nx = loc["nx"]
        ny = loc["ny"]
        
        # 1. 월별 누적 데이터를 저장할 하위 폴더 및 파일 경로 설정 (실황 데이터는 _current.csv 형태로 구분)
        monthly_dir_path = os.path.join(BASE_DIR, f"{loc_name}_{nx}_{ny}")
        os.makedirs(monthly_dir_path, exist_ok=True)
        monthly_csv = os.path.join(monthly_dir_path, f"{loc_name}_{nx}_{ny}_{year_month_str}_current.csv")
        
        # 2. 가장 최신 실황 상태 1줄만 보관할 파일 경로 설정 (덮어쓰기용)
        latest_csv = os.path.join(LATEST_DIR, f"{loc_name}_{nx}_{ny}_current_latest.csv")
        
        # 기상청 API 요청 URL 조합 (서비스 키, 페이지, 행 수, 응답 형식, 발표일시, 격자 좌표 포함)
        full_url = f"{API_BASE_URL}?serviceKey={SERVICE_KEY}&pageNo=1&numOfRows=1000&dataType=JSON&base_date={base_date_str}&base_time={base_time_str}&nx={nx}&ny={ny}"
        
        print(f"📍 [{loc_name} (NX:{nx}, NY:{ny})] 실황 조회 중 ({base_date_str} {base_time_str})...")
        
        try:
            # API 서버로 HTTP GET 요청 전송 및 응답 데이터(JSON) 파싱
            response = requests.get(full_url)
            response.raise_for_status()
            data = response.json()
            
            # API 응답 헤더의 결과 코드 확인 ("00"이 정상 응답)
            result_code = data.get("response", {}).get("header", {}).get("resultCode")
            if result_code != "00":
                msg = data.get("response", {}).get("header", {}).get("resultMsg", "알 수 없는 에러")
                print(f"❌ [{loc_name}] API 에러 발생: {msg}\n")
                continue
                
            # 응답 본문에서 실황 관측 아이템 리스트 추출 후 Pandas DataFrame으로 변환
            items = data["response"]["body"]["items"]["item"]
            df = pd.DataFrame(items)
            
            # 실황 데이터 카테고리(기온, 습도, 풍속 등)가 세로로 나열되어 있으므로 관측값(obsrValue)을 기준으로 가로로 피벗(Pivot)
            pivot_df = df.pivot(index=["baseDate", "baseTime", "nx", "ny"], columns="category", values="obsrValue").reset_index()
            pivot_df.columns.name = None
            
            # 데이터가 비어있는 경우 예외 처리
            if pivot_df.empty:
                print(f"⚠️ [{loc_name}] 조회된 실황 데이터가 없습니다.\n")
                continue
                
            sub = pivot_df.iloc[0]
            
            # 수집된 실황 데이터를 사람이 읽기 좋고 깔끔한 컬럼명으로 매핑하여 1차원 딕셔너리로 구성
            row_data = {
                "수집시각": now.strftime("%Y-%m-%d %H:%M:%S"),
                "발표일자": sub.get("baseDate"),
                "발표시각": sub.get("baseTime"),
                "격자X": nx,
                "격자Y": ny,
                "기온(℃)[T1H]": sub.get("T1H"),
                "습도(%)[REH]": sub.get("REH"),
                "1시간강수량[RN1]": sub.get("RN1"),
                "강수형태[PTY]": PTY_MAP.get(str(sub.get("PTY")), "기타"),
                "풍속(m/s)[WSD]": sub.get("WSD"),
                "풍향(deg)[VEC]": sub.get("VEC"),
                "동서바람[UUU]": sub.get("UUU"),
                "남북바람[VVV]": sub.get("VVV")
            }
            
            # 완성된 단일 행 데이터를 DataFrame으로 변환
            result_df = pd.DataFrame([row_data])
            
            # --- A. 월별 CSV 파일 누적 저장 (Append 모드) ---
            file_exists = os.path.exists(monthly_csv)
            file_empty = file_exists and os.path.getsize(monthly_csv) == 0

            if not file_exists or file_empty:
                # 파일이 없거나 비어 있으면 헤더를 포함하여 새로 생성
                result_df.to_csv(monthly_csv, index=False, encoding='utf-8-sig')
                print(f"✅ [{loc_name}] 월별 누적 파일 생성: {monthly_csv}")
            else:
                # 이미 존재할 경우 헤더 없이 데이터만 이어서 추가(Append)
                result_df.to_csv(monthly_csv, mode='a', index=False, header=False, encoding='utf-8-sig')
                print(f"✅ [{loc_name}] 월별 누적 데이터 추가 완료")
                
            # --- B. 최신 실황 데이터 1줄 파일 갱신 (Overwrite 덮어쓰기 모드) ---
            result_df.to_csv(latest_csv, index=False, encoding='utf-8-sig')
            print(f"✨ [{loc_name}] 최신 1줄 파일 갱신 완료: {latest_csv}")
                
        except Exception as e:
            # 네트워크 오류, 파싱 오류 등 예외 발생 시 에러 메시지 출력 후 다음 지역으로 진행
            print(f"❌ [{loc_name}] 예외 발생: {e}")
            
        print("-" * 40)

if __name__ == "__main__":
    fetch_and_save_current_weather()