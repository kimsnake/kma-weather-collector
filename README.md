# ⛅ KMA Weather Data Pipeline

기상청 공공데이터 API(초단기실황, 초단기예보, 단기예보)를 활용하여 주요 지역의 기상 데이터를 자동으로 수집하고, 로컬 CSV 누적 및 최신 상태(`latest`)를 관리하는 파이프라인 프로젝트입니다.

---
🔗 Live Demo: 날씨 대시보드 바로가기

## 🚀 Key Features

* **자동 수집 파이프라인:** 단기예보 및 실황 데이터를 주기적으로 안전하게 수집
* **시간대 최적화 로직:** 기상청 정기 발표 시간대에 맞춰 넉넉하고 유연하게 데이터를 조회 및 필터링
* **이중 데이터 관리:** 
  * 월별 누적 데이터 (`weather_vilage_data/` 등)
  * 프론트엔드 연동용 최신 1줄 덮어쓰기 데이터 (`latest_weather_data/`)
* **환경 변수 보안:** `python-dotenv`와 GitHub Actions Secrets를 연동하여 안전한 API Key 관리

---

## 📂 Project Structure

```text
kma-weather-collector/
├── .github/workflows/        # GitHub Actions 자동화 워크플로우
├── config.py                 # 환경변수 및 지역(NX, NY), 코드 매핑 설정
├── vilage_collector.py       # 단기예보 수집 스크립트
├── current_collector.py      # 초단기실황 수집 스크립트
├── pyproject.toml            # uv 패키지 매니저 의존성 정의
├── uv.lock                   # 의존성 락 파일
└── .env                      # 로컬 환경변수 (Git 제외)
