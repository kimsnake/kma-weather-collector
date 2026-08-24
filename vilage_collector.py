from datetime import datetime, timedelta
import os
import pandas as pd
from zoneinfo import ZoneInfo
from config import TARGET_LOCATIONS, SERVICE_KEY, SKY_MAP, PTY_MAP, LATEST_DIR
requests = __import__("requests")

# --- 1. 설정 정보 ---
API_BASE_URL = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst"
BASE_DIR = "weather_vilage_data" 

# 한국 시간(KST) 타임존 설정
KST = ZoneInfo("Asia/Seoul")

def check_vilage_base_time_generous():
    """
    현재 시각(KST)의 '시(hour)'가 단기예보 정기 발표 시간대(02, 05, 08, 11, 14, 17, 20, 23시)에 
    해당하기만 하면 분 단위 상관없이 넉넉하게 해당 발표 회차를 반환합니다.
    """
    now = datetime.now(KST)
    hour = now.hour

    # 단기예보 정기 발표 시간 목록 (시 단위)
    base_hours = [2, 5, 8, 11, 14, 17, 20, 23]

    # 현재 시간이 정기 발표 시간대에 포함되지 않으면 패스
    if hour not in base_hours:
        print(f"[{now.strftime('%Y-%m-%d %H:%M:%S')} KST] ⏳ 현재 시간({hour}시)은 정기 발표 시간이 아니므로 패스합니다.")
        return None, None

    # 새벽 2시 정기 발표인 경우 날짜 처리
    target_date = now
    if hour < 2:
        target_date = now - timedelta(days=1)

    return target_date.strftime("%Y%m%d"), f"{hour:02d}00"


def fetch_and_save_vilage_weather():
    now = datetime.now(KST)
    
    # 시간대 조건만 맞으면 넉넉하게 발표 시간 가져오기 (아니면 패스)
    base_date_str, base_time_str = check_vilage_base_time_generous()
    if not base_date_str or not base_time_str:
        return

    year_month_str = now.strftime("%Y%m")
    os.makedirs(LATEST_DIR, exist_ok=True)

    print(
        f"[{now.strftime('%Y-%m-%d %H:%M:%S')} KST] 🔍 [정기발표 시간대 일치] 단기예보 수집 시작 (Base: {base_date_str} {base_time_str})...\n"
    )

    for loc in TARGET_LOCATIONS:
        loc_name = loc["name"]
        nx = loc["nx"]
        ny = loc["ny"]

        monthly_dir_path = os.path.join(BASE_DIR, f"{loc_name}_{nx}_{ny}")
        os.makedirs(monthly_dir_path, exist_ok=True)
        monthly_csv = os.path.join(
            monthly_dir_path, f"{loc_name}_{nx}_{ny}_{year_month_str}_vilage.csv"
        )
        latest_csv = os.path.join(
            LATEST_DIR, f"{loc_name}_{nx}_{ny}_vilage_latest.csv"
        )

        full_url = f"{API_BASE_URL}?serviceKey={SERVICE_KEY}&pageNo=1&numOfRows=1500&dataType=JSON&base_date={base_date_str}&base_time={base_time_str}&nx={nx}&ny={ny}"

        print(f"📍 [{loc_name} (NX:{nx}, NY:{ny})] 단기예보 조회 중...")

        try:
            response = requests.get(full_url)
            response.raise_for_status()
            data = response.json()

            header = data.get("response", {}).get("header", {})
            if header.get("resultCode") != "00":
                print(
                    f"❌ [{loc_name}] API 에러 발생: {header.get('resultMsg')}\n"
                )
                continue

            items = (
                data.get("response", {})
                .get("body", {})
                .get("items", {})
                .get("item", [])
            )
            if not items:
                print(f"⚠️ [{loc_name}] 수집된 데이터가 없습니다.\n")
                continue

            df = pd.DataFrame(items)

            pivot_df = df.pivot_table(
                index=["fcstDate", "fcstTime"],
                columns="category",
                values="fcstValue",
                aggfunc="first",
            ).reset_index()
            pivot_df.columns.name = None

            row_data = {
                "수집시각": now.strftime("%Y-%m-%d %H:%M:%S"),
                "발표일자": base_date_str,
                "발표시각": base_time_str,
                "격자X": nx,
                "격자Y": ny,
            }

            pivot_df["dateTime"] = pd.to_datetime(pivot_df["fcstDate"] + pivot_df["fcstTime"], format='%Y%m%d%H%M')
            pivot_df = pivot_df.sort_values("dateTime")

            for idx, (_, sub) in enumerate(pivot_df.iterrows(), start=1):
                dt_obj = sub["dateTime"]
                formatted_time = dt_obj.strftime("%m-%d %H:%M") # 월-일 시:분 형태로 보기 좋게 매핑
                
                row_data[f"+{idx}_예보시각"] = formatted_time
                row_data[f"+{idx}_기온[TMP]"] = sub.get("TMP")
                row_data[f"+{idx}_습도[REH]"] = sub.get("REH")
                row_data[f"+{idx}_강수확률[POP]"] = sub.get("POP")
                row_data[f"+{idx}_하늘상태[SKY]"] = SKY_MAP.get(
                    str(sub.get("SKY")), "기타"
                )
                row_data[f"+{idx}_강수형태[PTY]"] = PTY_MAP.get(
                    str(sub.get("PTY")), "기타"
                )

            result_df = pd.DataFrame([row_data])

            # --- A. 월별 누적 저장 (Append) ---
            file_exists = os.path.exists(monthly_csv)
            file_empty = file_exists and os.path.getsize(monthly_csv) == 0

            if not file_exists or file_empty:
                result_df.to_csv(
                    monthly_csv, index=False, encoding="utf-8-sig"
                )
                print(f"✅ [{loc_name}] 월별 누적 파일 생성: {monthly_csv}")
            else:
                result_df.to_csv(
                    monthly_csv,
                    mode="a",
                    index=False,
                    header=False,
                    encoding="utf-8-sig",
                )
                print(f"✅ [{loc_name}] 월별 누적 데이터 추가 완료")

            # --- B. 최신 1줄 덮어쓰기 ---
            result_df.to_csv(latest_csv, index=False, encoding="utf-8-sig")
            print(
                f"✨ [{loc_name}] 최신 단기예보 1줄 갱신 완료 (총 {len(pivot_df)}개 타임라인 수록)"
            )

        except Exception as e:
            print(f"❌ [{loc_name}] 예외 발생: {e}")

        print("-" * 40)


if __name__ == "__main__":
    fetch_and_save_vilage_weather()