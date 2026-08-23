import os
from dotenv import load_dotenv

# 로컬 개발 환경인 경우 .env 파일을 로드합니다 (깃허브 액션 등에서는 .env 파일이 없어도 에러 없이 넘어감)
load_dotenv()

# 환경변수에서 KMA_SERVICE_KEY를 가져옵니다.
SERVICE_KEY = os.environ.get("KMA_SERVICE_KEY")

# 만약 환경변수가 등록되어 있지 않은 경우의 예외 처리 (필요시 콘솔 경고 출력)
if not SERVICE_KEY:
    print("⚠️ 경고: KMA_SERVICE_KEY 환경변수가 설정되지 않았습니다. API 호출 시 인증 에러가 발생할 수 있습니다.")

# 공통 조회 지역 리스트 (서울_대치동, 성남, 익산, 전주)
TARGET_LOCATIONS = [
    {"name": "서울_대치동", "nx": "61", "ny": "126"},
    {"name": "성남", "nx": "55", "ny": "127"},
    {"name": "익산", "nx": "63", "ny": "104"},
    {"name": "전주", "nx": "63", "ny": "89"},
]

# 하늘상태(SKY) 코드 매핑
SKY_MAP = {
    "1": "맑음(1)", 
    "3": "구름많음(3)", 
    "4": "흐림(4)"
}

# 강수형태(PTY) 코드 매핑
PTY_MAP = {
    "0": "없음(0)", 
    "1": "비(1)", 
    "2": "비/눈(2)", 
    "3": "눈(3)",
    "4": "소나기(4)", 
    "5": "빗방울(5)", 
    "6": "빗방울눈날림(6)", 
    "7": "눈날림(7)"
}

# 최신 데이터 1줄 저장 폴더 경로
LATEST_DIR = "latest_weather_data"