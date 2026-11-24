# 현재 테스트 계획과 검사 근거

## 대상과 전략

| 대상 | 검사 |
| --- | --- |
| 입력·구간 | 프롬프트·이미지 형식/크기, 10·20·30초의 정확한 10초 구간 수, 모델 형식 오류 거부 |
| 외부 API 경계 | 합성 키와 `httpx.MockTransport`로 고정 OpenAI endpoint·모델, 첨부 이미지 편집 요청, 서버 전용 키 읽기·중복 거부 검사. 실제 유료 API는 호출하지 않음 |
| 사람 승인·상태 | 명시 버튼 전 provider 호출 없음, 미생성/최종 승인 구분, 입력·예시·승인·영상 변조 거부, 실패 뒤 자동 재시도 없음 |
| 로컬 HTTP | CSRF 누락 403, 정상 단계 API·MP4 MIME 다운로드. Host/Origin 악성 값·보안 헤더는 아직 테스트로 assert하지 않음 |
| MP4 | 설치된 로컬 FFmpeg로 30초 H.264 결과 생성. `render()`가 FFprobe로 길이·720×1280·코덱을 확인하며 테스트는 반환 MP4 헤더를 확인. 10·20초 실제 렌더와 독립 FFprobe assert는 미실행 |
| 설계 동기화 | `tests/test_architecture_sync.py`와 가드로 구현 변경에 규칙/아키텍처 문서 동반 여부 확인. 문서 내용의 정확성은 별도 읽기 검토 |

## 실행 명령

저장소 루트의 Python 3.12 가상환경에서 실행한다. `FFMPEG_BIN`은 FFmpeg·FFprobe가 들어 있는 실제 폴더로 지정한다. 이 PC에서는 아래 경로의 FFmpeg 9.0.2를 사용했다.

```powershell
$env:FFMPEG_BIN = 'C:\Users\Administer\anaconda3\envs\llm\Library\bin'
.\.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -v
.\.venv\Scripts\python.exe scripts/check_architecture_sync.py --base HEAD
node --check web/storyboard.js
git diff --check
```

2026-11-24 이전 기능 제거 후보에서 `test_storyboard.py` **10개**와 `test_architecture_sync.py` **5개**가 각각 종료 0으로 통과했다. 새 런타임 네 모듈의 import 검사도 종료 0이다. 이 기록 이후 문서·파일 제거가 더 진행되므로 최종 후보의 재검사 결과는 해당 작업의 `workspace/legacy-removal-20261124/checks.md`를 따른다. 이전 회차에서 기본 입력 브라우저 화면을 확인했으나 삭제 후 전체 유료 생성 흐름을 브라우저에서 새로 실행한 것은 아니다.

실제 OpenAI 계정 권한·유료 호출·생성 이미지 품질·실사진 일관성·요금, 사용자 시청/수락, 10·20초 실제 MP4는 미검증이다. 검사 실패는 자동 재시도하지 않고 [workflow](workflow.md)의 회차 한도와 기록을 따른다.
