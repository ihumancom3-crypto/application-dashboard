# 신청 현황판

구글 스프레드시트에 쌓이는 캠프/클래스 신청자 데이터를 읽어서 신청 총합, 입금 완료, 미입금/대기, 명상경험별 인원을 자동으로 보여주는 Streamlit 웹앱입니다.

인증정보가 없거나 구글 시트 연결에 실패해도 앱은 멈추지 않고 샘플 데이터 모드로 실행됩니다.

## 실행 방법

1. 이 폴더에서 터미널을 엽니다.
2. 필요한 라이브러리를 설치합니다.

```bash
pip install -r requirements.txt
```

3. 앱을 실행합니다.

```bash
streamlit run app.py --server.port 8501 --server.address 127.0.0.1
```

4. 브라우저에서 아래 주소를 엽니다.

```text
http://127.0.0.1:8501
```

## 앱 사용 방법

왼쪽 사이드바에서 데이터 연결 방식을 고릅니다.

- 샘플 데이터: 구글 시트 없이 바로 테스트합니다.
- 공개 CSV 링크: 공개된 구글 시트 URL 또는 CSV export URL을 읽습니다.
- 서비스 계정: 비공개 구글 시트를 서비스 계정 인증으로 읽습니다.

과정명/차수는 직접 입력하지 않습니다. 앱이 시트 데이터를 읽고, 화면의 필터에서 선택할 수 있게 보여줍니다.

## 샘플 데이터 모드

처음 실행하면 기본으로 샘플 데이터가 사용됩니다. 샘플 데이터는 16명이며 아래 결과가 나와야 합니다.

```text
신청 총합 16명 / 입금 13명
신규 7 / 휴면 1
과정생 6 / 미파악 2
```

구글 시트 URL이 틀렸거나 인증정보가 없을 때도 앱은 샘플 데이터 모드로 전환됩니다.

## 공개 CSV 링크 방식

공개 CSV 링크 방식은 구글 시트를 공개해도 되는 경우에만 사용하세요.

1. 구글 스프레드시트를 엽니다.
2. 공유 설정을 `링크가 있는 모든 사용자 보기 가능`으로 바꾸거나, `파일 > 공유 > 웹에 게시`를 사용합니다.
3. 앱 사이드바에서 `공개 CSV 링크`를 선택합니다.
4. 구글 시트 URL을 입력합니다. 여러 시트를 연결하려면 URL을 한 줄에 하나씩 입력합니다.

일반 구글 시트 URL을 넣어도 앱이 CSV export URL로 변환을 시도합니다.

예시:

```text
https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit#gid={gid}
```

앱 내부 변환:

```text
https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv&gid={gid}
```

gid가 없으면 `gid=0`으로 처리합니다.

2개 이상 시트를 공개 CSV 방식으로 연결하는 예시:

```text
https://docs.google.com/spreadsheets/d/첫번째스프레드시트ID/edit#gid=0
https://docs.google.com/spreadsheets/d/두번째스프레드시트ID/edit#gid=0
```

각 시트 안에 `과정명` 또는 `캠프명` 같은 열이 있으면 앱이 그 열을 과정명/차수 필터로 사용합니다. 그런 열이 없으면 앱이 붙여주는 `데이터출처` 열을 필터로 사용할 수 있습니다.

## 서비스 계정 방식

서비스 계정 방식은 비공개 구글 시트를 안정적으로 읽기 위한 방법입니다. 초보자에게는 단계가 조금 길지만, 한번 설정하면 업무용으로 쓰기 좋습니다.

1. [Google Cloud Console](https://console.cloud.google.com/)에 접속합니다.
2. 새 프로젝트를 만듭니다.
3. `API 및 서비스 > 라이브러리`에서 `Google Sheets API`를 검색해 활성화합니다.
4. `API 및 서비스 > 사용자 인증 정보`로 이동합니다.
5. `사용자 인증 정보 만들기 > 서비스 계정`을 선택합니다.
6. 서비스 계정을 만든 뒤, 해당 서비스 계정의 `키` 탭에서 JSON 키를 발급받습니다.
7. JSON 파일을 열어 `client_email` 값을 확인합니다.
8. 실제 구글 스프레드시트를 열고 `공유` 버튼을 누릅니다.
9. `client_email` 주소를 공유 대상자로 추가하고 보기 권한을 줍니다.
10. 이 프로젝트 폴더에 `.streamlit/secrets.toml` 파일을 만듭니다.
11. 발급받은 JSON 내용을 `secrets.toml`에 옮겨 적습니다.

절대 인증 키를 외부에 공유하지 마세요. `secrets.toml`, JSON 키 파일, `credentials.json`은 GitHub나 메신저에 올리면 안 됩니다.

## secrets.toml 설정 예시

`.streamlit/secrets.toml.example` 파일을 참고해서 `.streamlit/secrets.toml` 파일을 만드세요. 예시 파일에는 실제 키가 들어 있지 않습니다.

```toml
[gcp_service_account]
type = "service_account"
project_id = "your-project-id"
private_key_id = "your-private-key-id"
private_key = "-----BEGIN PRIVATE KEY-----\nYOUR_PRIVATE_KEY\n-----END PRIVATE KEY-----\n"
client_email = "your-service-account@your-project.iam.gserviceaccount.com"
client_id = "your-client-id"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "your-cert-url"

[google_sheet]
spreadsheet_id = "your-spreadsheet-id"
worksheet_name = "시트1"
```

서비스 계정 방식으로 실행할 때는 앱 사이드바에서 `서비스 계정`을 선택합니다. `spreadsheet_id`는 구글 시트 주소에서 `/d/` 뒤와 `/edit` 앞 사이의 긴 문자열입니다.

한 스프레드시트 안에 워크시트가 2개 있는 경우:

```text
서비스 계정용 spreadsheet_id 또는 시트 URL:
your-spreadsheet-id

워크시트 이름:
마인드PT 3차
마인드PT 4차
```

스프레드시트 파일이 2개이고 워크시트 이름이 같은 경우:

```text
서비스 계정용 spreadsheet_id 또는 시트 URL:
first-spreadsheet-id
second-spreadsheet-id

워크시트 이름:
시트1
```

스프레드시트 파일도 2개이고 워크시트 이름도 각각 다른 경우:

```text
서비스 계정용 spreadsheet_id 또는 시트 URL:
first-spreadsheet-id
second-spreadsheet-id

워크시트 이름:
마인드PT 3차
마인드PT 4차
```

위처럼 개수를 맞춰 입력하면 첫 번째 ID는 첫 번째 워크시트, 두 번째 ID는 두 번째 워크시트와 연결됩니다.

## 환경변수 사용

원하면 `secrets.toml` 대신 환경변수를 사용할 수 있습니다.

- `GOOGLE_SERVICE_ACCOUNT_JSON`: 서비스 계정 JSON 전체 문자열
- `GOOGLE_SHEET_SPREADSHEET_ID`: 구글 스프레드시트 ID
- `GOOGLE_SHEET_WORKSHEET_NAME`: 워크시트 이름
- `GOOGLE_SHEET_URL`: 공개 CSV 링크 방식에서 기본 입력값

여러 워크시트 이름은 쉼표나 줄바꿈으로 구분할 수 있습니다.

## 구글 시트 열 이름 예시

앱은 아래와 같은 열 이름을 자동으로 추정합니다. 자동 추정이 틀리면 왼쪽 사이드바에서 직접 열을 선택하세요.

- 이름: 이름, 성명, 신청자명, 참가자명
- 과정명/차수: 과정, 과정명, 프로그램, 프로그램명, 캠프, 캠프명, 차수, 클래스명
- 입금 여부: 입금, 입금여부, 결제, 결제상태, 결제 여부, 상태
- 명상경험: 명상경험, 명상 경험, 경험여부, 수련경험, 수련 경험, 구분, 회원구분

입금 완료로 처리되는 값:

```text
입금, 입금완료, 완료, 결제완료, O, o, 예, Y, y, paid, Paid
```

미입금/대기로 처리되는 값:

```text
미입금, 대기, 결제대기, 미완료, X, x, 아니오, N, n, unpaid, Unpaid
```

명상경험은 `신규`, `휴면`, `과정생`, `미파악`으로 집계됩니다. 비어 있거나 알 수 없는 값은 `미파악`으로 처리됩니다.

현재 기본 연결 시트에서는 아래 기준으로 집계합니다.

- 신청 총합: `이름` 열이 비어 있지 않은 행만 계산합니다.
- 입금 완료: `결제 여부` 값이 `입금`이면 입금 완료로 계산합니다.
- 미입금/대기: `결제 여부` 값이 비어 있으면 미입금/대기로 계산합니다.
- 과정생: `1과정`부터 `7과정`, `희망`, `희망반`, `행복`, `행복반` 값을 과정생으로 계산합니다.

## 자주 발생하는 오류와 해결 방법

### 공개 CSV 링크를 읽을 수 없어요

- 구글 시트 공유 권한이 공개인지 확인하세요.
- 일반 URL을 넣었다면 주소에 `/spreadsheets/d/`가 포함되어 있는지 확인하세요.
- 회사나 학교 계정의 보안 정책 때문에 공개 CSV 접근이 막힐 수 있습니다.

### 서비스 계정 연결이 실패해요

- Google Sheets API가 활성화되어 있는지 확인하세요.
- 구글 시트에 서비스 계정의 `client_email`을 공유했는지 확인하세요.
- `.streamlit/secrets.toml` 파일 이름과 위치가 정확한지 확인하세요.
- `private_key` 안의 줄바꿈은 `\n` 형태로 들어가야 합니다.

### 열이 잘못 인식돼요

왼쪽 사이드바의 `열 선택` 영역에서 이름, 과정명/차수, 입금 여부, 명상경험 열을 직접 선택하세요.

### 그래도 앱이 멈추나요?

구글 시트 연결에 실패하면 앱은 샘플 데이터로 전환되도록 만들어져 있습니다. 오류 안내가 보이면 샘플 데이터로 화면이 뜨는지 먼저 확인한 뒤, 시트 설정을 다시 점검하세요.

## 다운로드 기능

앱에서 담당자 공유용 문구를 TXT 또는 Markdown 파일로 다운로드할 수 있습니다. 집계 결과도 CSV 파일로 다운로드할 수 있습니다.

## 배포해서 공유하는 방법

가장 쉬운 방법은 Streamlit Community Cloud를 사용하는 것입니다.

1. GitHub에 새 저장소를 만듭니다.
2. 이 프로젝트의 `app.py`, `requirements.txt`, `README.md`, `.gitignore`, `.streamlit/secrets.toml.example` 파일을 올립니다.
3. `.streamlit/secrets.toml` 파일은 올리지 않습니다.
4. [Streamlit Community Cloud](https://streamlit.io/cloud)에 GitHub 계정으로 로그인합니다.
5. `Create app` 또는 `New app`을 누릅니다.
6. GitHub 저장소, branch, main file path를 선택합니다.
7. main file path는 `app.py`로 지정합니다.
8. Deploy를 누릅니다.
9. 배포가 끝나면 `https://앱이름.streamlit.app` 형태의 공유 링크가 생깁니다.

현재 앱은 공개 CSV 링크 방식으로 구글시트를 읽기 때문에 별도 secrets 설정 없이 배포할 수 있습니다. 나중에 서비스 계정 방식으로 바꾸면 Streamlit Cloud의 Secrets 설정에 인증정보를 넣어야 합니다.

### 계정 없이 잠깐 공유하는 방법

GitHub 계정이 아직 없다면 Cloudflare Quick Tunnel로 현재 PC에서 실행 중인 앱을 임시 공개 URL로 공유할 수 있습니다.

```bash
cloudflared tunnel --url http://127.0.0.1:8501
```

이 방식은 계정 없이 빠르게 공유할 수 있지만 테스트용입니다. PC가 꺼지거나 터널 프로그램이 종료되면 링크가 끊기고, 다시 실행하면 주소가 바뀔 수 있습니다. 오래 쓰는 고정 링크가 필요하면 Streamlit Community Cloud 같은 정식 배포 방식이 좋습니다.

## 나중에 추가하면 좋은 기능

- 아침/저녁 자동 알림
- 카카오톡 자동 발송
- 문자 자동 발송
- Gmail 자동 발송
- 일자별 신청 추이
- 입금 누락자 자동 표시
- 미파악 대상자 자동 알림
- 여러 캠프 통합 대시보드
- 관리자 권한
- 기록 저장
- 배포용 보안 설정
