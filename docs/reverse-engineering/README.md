# 현재 구현 역공학 설계 문서

대상은 2026-11-24 로컬 작업본의 **8766 GPT 스토리보드 작업실**이다. 이전 실행 코드는 사용자 결정에 따라 제거했고 처음 구상한 하네스 문서는 이력으로 보존했다. 이 문서는 현재 소스에서 확인한 호출·저장·승인 경로를 설명한다. 실제 OpenAI 유료 요청과 사용자 이미지 품질은 검증하지 않았다.

## 읽는 순서

1. [시스템 개념도](system-concept.md): 사용자 요청부터 OpenAI, 로컬 저장, MP4 출력까지.
2. [클래스·모듈 다이어그램](class-diagram.md): 각 Python 구성 요소의 소유와 호출 관계.
3. 주요 기능 시퀀스: [입력·프롬프트 보강](sequence-plan.md) → [예시 이미지](sequence-previews.md) → [최종 결정·MP4](sequence-render.md).
4. [데이터·상태 수명주기](data-and-state.md): 작업 JSON, 승인 결속, 실패 상태, 길이 계산.
5. [HTTP 경계·보안](api-and-security.md): 고정 라우트, 키/이미지 전송, 검증 범위.

## 한눈에 보는 실제 구조

브라우저는 [로컬 서버](../../storyboard_web.py#L40)에 요청한다. [StoryboardService](../../src/storyboard_flow.py#L39)가 작업 상태와 사용자의 단계별 선택을 관리한다. 명시 버튼에서만 [OpenAI 어댑터](../../src/storyboard_openai.py#L58)가 GPT/이미지 API를 호출한다. 승인 후 [로컬 렌더러](../../src/storyboard_render.py#L64)가 FFmpeg와 FFprobe로 무음 MP4를 만든다. 데이터베이스는 없고 `workspace/storyboards/` 아래 작업별 JSON·이미지·MP4 파일이 저장소다.

**관찰됨:** 코드 경로, 10·20·30초 계약, 승인/변조 검사, 모의 HTTP와 30초 로컬 FFmpeg 테스트. **미확인:** 실제 OpenAI 응답·요금, 생성 이미지의 일관성, 브라우저 전체 유료 흐름, 10·20초 실제 렌더. 제안서의 TTS·자막·배포·다중 사용자 서비스는 현재 구현에 없다. [테스트 범위](../testing.md)
