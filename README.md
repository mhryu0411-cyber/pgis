# pgis

동국대학교 참여형 지도 제작 특강

## 기상청 ASOS 시간자료 설정

공공데이터포털의 `기상청_지상(종관, ASOS) 시간자료 조회서비스` 활용신청 후
발급받은 일반 인증키(Encoding 또는 Decoding)를 환경변수로 설정합니다.

```powershell
$env:KMA_ASOS_SERVICE_KEY="발급받은_인증키"
```

Railway에서는 Variables에 다음처럼 등록합니다.

- 이름: `KMA_ASOS_SERVICE_KEY`
- 값: 발급받은 인증키만 입력하며 앞뒤 따옴표는 넣지 않음

변수 저장 후 반드시 새 배포가 완료되어야 앱 프로세스가 값을 읽습니다. 인증키를
발급받은 것과 별개로 공공데이터포털에서 해당 ASOS API의 활용신청 상태가
`승인`인지도 확인해야 합니다.

기본 관측지점은 제주 ASOS `184`번입니다. 필요하면 다음 환경변수로 변경할 수
있습니다.

```powershell
$env:KMA_ASOS_STATION_ID="184"
$env:KMA_ASOS_STATION_NAME="제주"
```

Streamlit 배포 환경에서는 같은 이름의 `KMA_ASOS_SERVICE_KEY`를 secrets에
등록해도 됩니다. 공공데이터포털 ASOS 시간자료 API는 전일(D-1)까지 조회할 수
있으므로 화면에는 최신 예보가 아니라 최근 시간별 관측값이 표시됩니다.
