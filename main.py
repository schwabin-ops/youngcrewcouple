import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# KOBIS 일별 박스오피스 API 주소입니다.
API_URL = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"

# 웹페이지의 기본 설정입니다.
st.set_page_config(
    page_title="어제의 박스오피스",
    page_icon="🎬",
    layout="wide",
)

st.title("🎬 어제의 박스오피스")
st.caption("영화진흥위원회(KOBIS) 일별 박스오피스 · 한국 시간 기준 어제 집계")

# 서버 시간이 어느 지역이든 한국 시간으로 날짜를 계산합니다.
korea_today = datetime.now(ZoneInfo("Asia/Seoul")).date()
yesterday = korea_today - timedelta(days=1)
target_date = yesterday.strftime("%Y%m%d")
st.write(f"조회 날짜: **{yesterday.strftime('%Y년 %m월 %d일')}**")

# 인증키는 코드에 직접 쓰지 않고 Streamlit의 Secrets에서 읽습니다.
try:
    api_key = st.secrets["KOBIS_KEY"]
except Exception:
    st.error("KOBIS 인증키를 찾을 수 없습니다.")
    st.markdown(
        "**확인 방법**\n"
        "1. Streamlit Cloud에서 앱의 **Settings → Secrets**를 엽니다.\n"
        '2. 아래와 같은 형식으로 발급받은 인증키를 저장합니다.\n'
        '   `KOBIS_KEY = "발급받은_인증키"`\n'
        "3. 저장한 뒤 앱을 다시 실행합니다. 인증키를 파이썬 코드에 직접 적지 마세요."
    )
    st.stop()

if not str(api_key).strip():
    st.error("KOBIS_KEY 값이 비어 있습니다. Streamlit Cloud의 Secrets 설정을 확인해 주세요.")
    st.stop()

# API를 요청하고, 연결 오류나 응답 형식 오류가 나면 안내합니다.
try:
    response = requests.get(
        API_URL,
        params={"key": str(api_key).strip(), "targetDt": target_date},
        timeout=20,
    )
    response.raise_for_status()
    data = response.json()
except requests.exceptions.Timeout:
    st.error("KOBIS API 응답 시간이 초과되었습니다.")
    st.info("인터넷 연결 상태를 확인한 뒤 잠시 후 새로고침해 주세요.")
    st.stop()
except requests.exceptions.HTTPError as exc:
    st.error(f"KOBIS API 요청에 실패했습니다. (HTTP 상태 코드: {response.status_code})")
    st.info("API 주소가 맞는지, KOBIS 서비스가 정상인지 확인한 뒤 다시 시도해 주세요.")
    st.stop()
except requests.exceptions.RequestException:
    st.error("KOBIS API에 연결하지 못했습니다.")
    st.info("네트워크 상태와 API 주소를 확인한 뒤 잠시 후 다시 시도해 주세요.")
    st.stop()
except ValueError:
    st.error("KOBIS API 응답을 JSON으로 읽을 수 없습니다.")
    st.info("API 응답 형식이나 KOBIS 서비스 상태를 확인해 주세요.")
    st.stop()

# KOBIS는 인증키가 잘못되어도 HTTP 상태 코드 200과 faultInfo를 보낼 수 있습니다.
if isinstance(data, dict) and data.get("faultInfo"):
    st.error("KOBIS API가 오류 내용을 반환했습니다. 인증키 또는 요청 조건을 확인해 주세요.")
    st.json(data["faultInfo"])
    st.markdown(
        "**확인할 항목**\n"
        "- Streamlit Cloud의 Secrets에 `KOBIS_KEY`가 정확히 저장되어 있는지\n"
        "- 인증키가 유효하고 KOBIS Open API 사용 신청이 승인되어 있는지\n"
        "- 요청 날짜가 `YYYYMMDD` 형식으로 전달되는지"
    )
    st.stop()

# 응답에 박스오피스 결과와 영화 목록이 있는지 확인합니다.
box_office = data.get("boxOfficeResult") if isinstance(data, dict) else None
if not isinstance(box_office, dict):
    st.error("API 응답에서 박스오피스 결과를 찾지 못했습니다.")
    st.info("KOBIS API 응답 구조와 서비스 상태를 확인해 주세요.")
    st.stop()

movies = box_office.get("dailyBoxOfficeList")
if not isinstance(movies, list) or len(movies) == 0:
    st.warning("해당 날짜의 영화 목록이 비어 있습니다.")
    st.markdown(
        "**확인할 항목**\n"
        "- 한국 시간 기준 어제의 박스오피스 자료가 등록되었는지\n"
        "- KOBIS에서 해당 날짜의 일별 박스오피스 자료를 제공하는지\n"
        "- 잠시 후 새로고침하면 자료가 표시되는지"
    )
    st.stop()

# API 숫자 값은 문자열로 오므로, 표와 그래프에서 쓰기 쉽게 숫자로 바꿉니다.
def to_int(value):
    try:
        return int(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return 0

rows = []
for movie in movies:
    rows.append(
        {
            "순위": to_int(movie.get("rank", 0)),
            "영화명": movie.get("movieNm") or "영화명 정보 없음",
            "개봉일": movie.get("openDt") or "-",
            "관객수": to_int(movie.get("audiCnt", 0)),
            "누적관객": to_int(movie.get("audiAcc", 0)),
            "스크린수": to_int(movie.get("scrnCnt", 0)),
        }
    )

# 순위 순서대로 정리하고, 표에서 숫자를 읽기 쉽게 표시합니다.
df = pd.DataFrame(rows).sort_values("순위").reset_index(drop=True)

# 1위 영화 정보를 지표 카드 3개로 크게 보여 줍니다.
first_movie = df.iloc[0]
st.subheader(f"🥇 박스오피스 1위: {first_movie['영화명']}")
metric1, metric2, metric3 = st.columns(3)
metric1.metric("일일 관객수", f"{first_movie['관객수']:,}명")
metric2.metric("누적 관객수", f"{first_movie['누적관객']:,}명")
metric3.metric("스크린 수", f"{first_movie['스크린수']:,}개")

st.divider()

# 관객수가 많은 상위 5편을 막대그래프로 표시합니다.
st.subheader("📊 관객수 상위 5편")
top5 = df.nlargest(5, "관객수").sort_values("관객수", ascending=False)
chart_data = top5.set_index("영화명")[["관객수"]]
st.bar_chart(chart_data)

# 요청한 항목들을 표로 표시합니다.
st.subheader("📋 일별 박스오피스 전체 목록")
display_df = df[["순위", "영화명", "개봉일", "관객수", "누적관객", "스크린수"]].copy()
for column in ["관객수", "누적관객", "스크린수"]:
    display_df[column] = display_df[column].map(lambda number: f"{number:,}")
st.dataframe(display_df, hide_index=True, use_container_width=True)

st.caption("자료 출처: 영화진흥위원회(KOBIS) Open API. 관객수와 스크린 수는 API 응답 기준입니다.")
