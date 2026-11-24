# 최종 결정·MP4 다운로드 시퀀스

사용자는 모든 예시 이미지와 프롬프트를 본 뒤 **영상 미생성** 또는 **최종 승인**을 선택한다. 서버는 `preview_ready`와 원본·예시 파일의 해시를 다시 확인하고, **그 시점에** 승인 내용의 해시를 생성한 후 렌더를 실행한다. [UI 선택](../../web/storyboard.js#L21) · [서버 승인](../../src/storyboard_flow.py#L233)

```mermaid
sequenceDiagram
    actor User as 사용자
    participant UI as 브라우저 UI
    participant HTTP as localhost Handler
    participant Service as StoryboardService
    participant Store as 작업 파일
    participant Render as storyboard_render
    participant FFmpeg as 로컬 FFmpeg/FFprobe
    alt 영상 미생성
      User->>UI: 미생성 클릭
      UI->>HTTP: POST /api/jobs/{id}/decline
      HTTP->>Service: decline(id)
      Service->>Store: stage=declined
      Service-->>UI: 종료 상태
    else 최종 승인
      User->>UI: 예시·프롬프트 승인 확인
      UI->>HTTP: POST /api/jobs/{id}/render
      HTTP->>Service: approve_and_render(id)
      Service->>Store: 원본·예시 해시 재검사
      Service->>Store: approval_sha256, stage=rendering
      Service->>Render: render(job_dir, segments, seconds)
      loop 각 10초 구간
        Render->>FFmpeg: PNG + motion → part-NN.mp4
      end
      Render->>FFmpeg: concat → video.mp4
      Render->>FFmpeg: FFprobe 길이·720×1280·H.264
      FFmpeg-->>Render: 검사 결과
      Render-->>Service: MP4 bytes
      Service->>Store: video SHA-256, stage=ready
      Service-->>UI: /media/{id}/video.mp4
      User->>UI: 다운로드
      UI->>HTTP: GET /media/{id}/video.mp4
      HTTP->>Service: media(id, video.mp4)
      Service->>Store: 파일 SHA-256 재검사
      Service-->>HTTP: MP4 bytes
      HTTP-->>User: attachment storyboard.mp4
    end
    opt 렌더 실패
      Service->>Store: stage=render_failed
      Service-->>UI: 오류, 자동 재시도 없음
    end
```

렌더러는 24fps에서 구간당 정확히 10초 분량을 요청한다. [상수](../../src/storyboard_render.py#L15) · [렌더 명령](../../src/storyboard_render.py#L64)

$$
N_{\mathrm{frames/segment}}=(10\,\mathrm{s})(24\,\mathrm{frames/s})=240\,\mathrm{frames}.
$$

FFprobe는 최종 MP4의 길이, 720×1280 해상도, H.264 코덱을 코드 내부에서 검사한다. 30초 합성은 로컬 테스트로 확인했으나 10·20초 실제 렌더와 사용자의 시청·수락은 미확인이다. [검사 코드](../../src/storyboard_render.py#L82) · [테스트](../../tests/test_storyboard.py#L213)
