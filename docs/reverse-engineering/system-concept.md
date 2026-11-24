# 시스템 개념도와 데이터 흐름

현재 앱은 한 PC의 127.0.0.1 서버와 브라우저에서 실행된다. 별도 DB·큐·백그라운드 작업자는 없다. `workspace/storyboards/`의 파일이 영속 작업 저장소다. [서버 생성](../../storyboard_web.py#L40) · [저장소 경로](../../src/storyboard_flow.py#L14)

```mermaid
flowchart LR
    U[사용자] -->|프롬프트·길이·선택 이미지| B[브라우저 UI]
    B -->|JSON / 명시 버튼| H[localhost 8766 Handler]
    H -->|상태 전환| S[StoryboardService]
    S <-->|state.json·원본·예시·MP4| FS[(로컬 파일 저장소)]
    S -->|보강 요청: 프롬프트·선택 이미지| P[OpenAIStoryboardProvider]
    P -->|HTTPS Responses| GPT[OpenAI GPT API]
    P -->|HTTPS Images / Edits| IMG[OpenAI 이미지 API]
    GPT -->|전체·구간 프롬프트와 이동| P
    IMG -->|구간별 PNG| P
    S -->|최종 승인 뒤만| R[로컬 FFmpeg·FFprobe]
    R -->|10초 조각·무음 MP4| FS
    H -->|프롬프트·예시·MP4 URL| B
    B -->|다운로드 GET /media/{id}/video.mp4| H
    H -->|MP4 bytes| B
    B -->|검토·다운로드| U
```

| 경계 | 실제 데이터·동작 | 근거 |
| --- | --- | --- |
| 사용자 → 브라우저 → 서버 | 프롬프트, 10·20·30초, 선택 이미지의 base64. 서버는 JSON 크기·필드와 이미지 형식/크기를 검사한다. | [UI 제출](../../web/storyboard.js#L19), [HTTP 입력](../../storyboard_web.py#L119), [입력 검증](../../src/storyboard_flow.py#L121) |
| 서버 → OpenAI | 보강에는 프롬프트·길이와 선택 이미지, 예시에는 구간 프롬프트와 선택 원본 이미지를 보낸다. 각 명시 버튼에서 동기 HTTPS 요청을 한다. | [보강/이미지 요청](../../src/storyboard_openai.py#L82), [UI 버튼](../../web/storyboard.js#L19) |
| 서버 ↔ 파일 저장소 | 작업별 `state.json`, 선택 `source.*`, `preview-NN.png`, `part-NN.mp4`, `video.mp4`를 읽고 쓴다. 데이터베이스는 사용하지 않는다. | [상태 저장](../../src/storyboard_flow.py#L96), [렌더 파일](../../src/storyboard_render.py#L64) |
| 서버 → 로컬 제작 → 사용자 | 모든 예시가 준비된 경우 최종 승인을 결속한 뒤 FFmpeg 합성/FFprobe 검사를 하고 고정 경로에서 MP4를 제공한다. | [승인·렌더](../../src/storyboard_flow.py#L233), [렌더 검사](../../src/storyboard_render.py#L64), [미디어 GET](../../storyboard_web.py#L92) |

브라우저의 확인 대화상자는 비용·제작 의사를 묻고, 서버는 작업 단계와 파일 해시를 다시 검사한다. 브라우저 확인만으로 서버 상태가 승인되는 것은 아니다. [UI 확인](../../web/storyboard.js#L20) · [서버 상태 검사](../../src/storyboard_flow.py#L233)

**미확인:** 외부 OpenAI 요청의 실제 성공·과금과 이미지 품질. 이 도식의 OpenAI 노드는 코드가 호출하도록 구성한 외부 경계이며 실서비스 성공을 뜻하지 않는다.
