"""Small disk-backed GUI coordinator around the existing offline contracts.

Only fixed actions and server-generated IDs cross the UI boundary. Approval is
an explicit action, never a side effect of preparing, viewing, or restarting.
"""

from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
from threading import Lock, RLock
from uuid import uuid4

from src.direction import _canonical, create_direction, create_prompts
from src.local_model_mock import draft_local_mock
from src.local_ollama import create_local_draft, MODEL, MODEL_DIGEST
from src.openai_mock import create_mock_draft
from src.research_mock import search_mock, validate_research
from src.mock_media import WORKSPACE, _result_dir, _file, _json_read, _json_write, produce_mock_media
from src.mock_production import (_digest, approve_mock_production, create_mock_quote,
                                 _timestamp, validate_mock_approval, validate_mock_quote)
from src.mock_rework import rework_plan_mock, prepare_rework_mock, produce_rework_mock
from src.quality_feedback import (inspect_mock_result, review_mock_result,
                                  validate_mock_inspection, validate_mock_review)
from src.shorts import approve_plan, create_draft, is_approved, revise_plan, validate_brief, validate_plan


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
# The pinned SDK mock temporarily isolates one module's environment view.
# Serialize GUI mock calls across Workflow instances so restoration cannot race.
_API_MOCK_LOCK = Lock()
_NO_RESEARCH = object()
PRICING = {"schema_version": 1, "source": "fictional_test_only", "unit": "mock_credit",
           "video_per_second": 2, "narration_per_100_characters": 1, "assembly_fixed": 5}
STATUS_ACTIONS = {
    "draft": ["approve_plan", "revise_draft"], "plan_approved": ["prepare"],
    "prepared": ["approve_production"], "production_approved": ["produce"],
    "result_pending": ["review"], "changes_requested": ["revise_result"],
    "accepted": [], "blocked": []}
FILES = {"draft.json", "plan.json", "direction.json", "prompts.json", "pricing.json",
         "quote.json", "approval.json", "inspection.json", "review.json", "revision.json",
         "handoff.json", "video.mp4", "subtitles.srt", "scenes.json", "quality.json",
         "manifest.json", "failure.json", "rework.json", "brief.json", "creation.json"}


def strict_json(data):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("중복 JSON 키는 사용할 수 없습니다.")
            result[key] = value
        return result
    def constant(value):
        raise ValueError("유한한 JSON 숫자만 사용할 수 있습니다.")
    return json.loads(data, object_pairs_hook=pairs, parse_constant=constant)


def fields(value, required):
    if not isinstance(value, dict) or set(value) != set(required):
        raise ValueError("요청 항목이 맞지 않습니다. 화면을 새로 고쳐 다시 확인하세요.")


def _path(value):
    return _result_dir(value, new=not Path(value).exists())


class Workflow:
    def __init__(self, base=None):
        self.base = _path(WORKSPACE / "gui" if base is None else base)
        self.base.mkdir(parents=True, exist_ok=True)
        self.lock = RLock()

    def folder(self, job):
        if not isinstance(job, str) or not re.fullmatch(r"[0-9a-f]{32}", job):
            raise ValueError("올바른 작업 ID가 아닙니다.")
        return _result_dir(self.base / job)

    def _read(self, folder, name):
        value = _json_read(_file(folder, name))
        if not isinstance(value, dict):
            raise ValueError("저장된 JSON은 객체여야 합니다. 손상된 작업을 보존하고 새 작업을 만드세요.")
        return value

    def _snapshot(self, folder):
        result = {}
        for path in sorted(folder.rglob("*")):
            if any(part.startswith(".") for part in path.relative_to(folder).parts):
                continue
            if path.name not in FILES:
                continue
            safe = _file(_result_dir(path.parent), path.name)
            result[safe.relative_to(folder).as_posix()] = sha256(safe.read_bytes()).hexdigest()
        return result

    def _event(self, folder, previous, status, revision, *, source=None, error=None):
        events = _path(folder / "events")
        events.mkdir(exist_ok=True)
        record = {"schema_version": 1, "sequence": 1 if previous is None else previous["sequence"] + 1,
                  "previous_sha256": None if previous is None else previous["content_sha256"],
                  "status": status, "revision": revision, "source": source,
                  "real_execution_allowed": False, "error": error,
                  "created_at": datetime.now(timezone.utc).isoformat(),
                  "files": self._snapshot(folder)}
        record["content_sha256"] = _digest(record)
        _json_write(events / f"{record['sequence']:06}.json", record)
        return record

    def _load(self, job):
        folder = self.folder(job)
        events = _result_dir(folder / "events")
        names = sorted(p.name for p in events.iterdir())
        if not names:
            raise ValueError("저장된 작업 기록이 없습니다.")
        previous = None
        for index, name in enumerate(names, 1):
            if name != f"{index:06}.json":
                raise ValueError("작업 기록 순서가 변경됐습니다.")
            item = self._read(events, name)
            fields(item, {"schema_version", "sequence", "previous_sha256", "status", "revision",
                          "source", "real_execution_allowed", "error", "created_at", "files", "content_sha256"})
            # Shape checks precede membership, arithmetic and downstream use.
            # A malformed job must not break the list of unrelated valid jobs.
            if (type(item["schema_version"]) is not int or item["schema_version"] != 1 or
                    type(item["sequence"]) is not int or item["sequence"] != index or
                    item["real_execution_allowed"] is not False or
                    not isinstance(item["status"], str) or item["status"] not in STATUS_ACTIONS or
                    type(item["revision"]) is not int or not 1 <= item["revision"] <= index or
                    (item["source"] is not None and (type(item["source"]) is not int or
                                                      not 1 <= item["source"] < item["revision"])) or
                    (item["error"] is not None and not isinstance(item["error"], str)) or
                    not isinstance(item["created_at"], str) or
                    not isinstance(item["files"], dict) or any(
                        not isinstance(path, str) or not isinstance(digest, str) or
                        re.fullmatch(r"[0-9a-f]{64}", digest) is None
                        for path, digest in item["files"].items()) or
                    not isinstance(item["content_sha256"], str) or
                    re.fullmatch(r"[0-9a-f]{64}", item["content_sha256"]) is None or
                    (item["previous_sha256"] is not None and (
                        not isinstance(item["previous_sha256"], str) or
                        re.fullmatch(r"[0-9a-f]{64}", item["previous_sha256"]) is None)) or
                    item["previous_sha256"] != (None if previous is None else previous["content_sha256"]) or
                    item["content_sha256"] != _digest({k: v for k, v in item.items() if k != "content_sha256"})):
                raise ValueError("작업 기록의 결속이 변경됐습니다.")
            if _timestamp(item["created_at"]) > datetime.now(timezone.utc):
                raise ValueError("작업 기록의 시각이 올바르지 않습니다.")
            previous = item
        if _canonical(previous["files"]) != _canonical(self._snapshot(folder)):
            raise ValueError("저장 파일이 변경됐거나 미완료 출력이 있습니다. 원본을 보존하고 새 작업을 만드세요.")
        return folder, previous

    @staticmethod
    def _revision(folder, number):
        return _path(folder / f"r{number:04}")

    def _values(self, folder):
        prepared = _result_dir(folder / "prepared")
        return tuple(self._read(prepared, name) for name in
                     ("plan.json", "direction.json", "prompts.json", "pricing.json", "quote.json"))

    def _source(self, root, source, revision):
        if type(source) is not int or not 1 <= source < revision:
            raise ValueError("수정 원본 연결이 올바르지 않습니다.")
        folder = self._revision(root, source)
        values = (*self._values(folder), self._read(folder, "approval.json"))
        result = _result_dir(folder / "result")
        inspection = self._read(folder, "inspection.json")
        review = self._read(folder, "review.json")
        return values, result, inspection, review

    def _current(self, root, event):
        folder = self._revision(root, event["revision"])
        draft = self._read(folder, "draft.json")
        validate_plan(draft)
        if draft["status"] != "draft" or draft["approval"] is not None:
            raise ValueError("저장된 초안은 미승인 상태여야 합니다.")
        if event["status"] not in ("draft", "blocked"):
            plan = self._read(folder, "plan.json")
            check = deepcopy(plan)
            check.update(status="draft", approval=None)
            if not is_approved(plan) or _canonical(check) != _canonical(draft):
                raise ValueError("기획 승인이 현재 초안과 일치하지 않습니다.")
            if event["status"] not in ("plan_approved",):
                values = self._values(folder)
                if _canonical(values[0]) != _canonical(plan):
                    raise ValueError("준비된 기획이 현재 승인과 다릅니다.")
                validate_mock_quote(values[4], *values[:4])
                if event["status"] in ("result_pending", "changes_requested", "accepted"):
                    approval = self._read(folder, "approval.json")
                    inspected = self._read(folder, "inspection.json")
                    validate_mock_inspection(inspected, *values, approval, folder / "result")
                    if event["status"] != "result_pending":
                        review = self._read(folder, "review.json")
                        validate_mock_review(review, *values, approval, folder / "result", inspected)
                        expected = "changes_requested" if event["status"] == "changes_requested" else "accepted_mock_result"
                        if review["status"] != expected:
                            raise ValueError("확인 기록과 작업 상태가 다릅니다.")
        return folder, draft

    def research(self, brief):
        fields(brief, {"topic", "target_seconds", "aspect_ratio", "style", "audience", "forbidden", "max_budget"})
        packet = search_mock(brief)
        validate_research(packet, brief, allow_empty=True)
        with self.lock:
            folder = _path(self.base / "research")
            folder.mkdir(exist_ok=True)
            identity = uuid4().hex
            _json_write(folder / f"{identity}.json", packet)
        return {"schema_version": 1, "id": identity, "packet": packet}

    def create(self, brief, mode, research_id=_NO_RESEARCH):
        if mode not in ("local_template", "local_model_mock", "local_ollama", "openai_mock"):
            raise ValueError("화면에 있는 기획 방식만 선택할 수 있습니다.")
        fields(brief, {"topic", "target_seconds", "aspect_ratio", "style", "audience", "forbidden", "max_budget"})
        research = None
        if research_id is not _NO_RESEARCH:
            if not isinstance(research_id, str) or re.fullmatch(r"[0-9a-f]{32}", research_id) is None:
                raise ValueError("자료 조사 결과를 다시 검색한 뒤 기획을 생성하세요.")
            try:
                research = self._read(_path(self.base / "research"), f"{research_id}.json")
                validate_research(research, brief)
            except (OSError, ValueError) as error:
                raise ValueError("자료 조사 결과가 없거나 입력 조건과 다릅니다. 다시 검색하거나 자료 조사를 끄세요.") from error
        options = {} if research is None else {"research": deepcopy(research)}
        if mode == "local_ollama":
            expected = deepcopy(validate_brief(brief))
            try:
                draft = create_local_draft(deepcopy(expected), **options)
                validate_plan(draft)
                if (draft["status"] != "draft" or draft.get("approval") is not None or
                        draft.get("cost_estimate") is not None or draft["brief"] != expected or
                        draft["source"] != f"ollama_local:{MODEL}@{MODEL_DIGEST}"):
                    raise ValueError("local planning response changed application-owned data")
            except ValueError as error:
                message = str(error)
                if "unavailable or timed out" in message:
                    detail = "Ollama 모델 서버에 연결하지 못했거나 응답 시간이 초과됐습니다. 모델 서버를 실행한 뒤 다시 시도하세요."
                elif "version does not match" in message or "not installed with the expected digest" in message:
                    detail = "실행 중인 Ollama와 설치된 모델이 이 프로젝트의 설정과 다릅니다. 기존 실행 안내를 확인하세요."
                else:
                    detail = "로컬 AI 응답이 기획 조건을 통과하지 못했습니다. 입력 조건을 확인한 뒤 다시 시도하세요."
                raise ValueError(detail + " 기존 작업은 유지되며 자동으로 다시 생성하지 않습니다.") from error
        elif mode == "openai_mock":
            expected = deepcopy(validate_brief(brief))
            try:
                with _API_MOCK_LOCK:
                    draft = create_mock_draft(deepcopy(expected), **options)
                validate_plan(draft)
                if (draft["status"] != "draft" or draft.get("approval") is not None or
                        draft.get("cost_estimate") is not None or draft["brief"] != expected or
                        draft["source"] != "openai_mock"):
                    raise ValueError("mock planning response changed application-owned data")
            except ValueError as error:
                raise ValueError("API 모의 응답이 기획 조건을 통과하지 못했습니다. 입력 조건을 확인한 뒤 다시 시도하세요. "
                                 "기존 작업은 유지되며 실제 API 호출이나 자동 재시도는 하지 않습니다.") from error
        else:
            draft = create_draft(brief, **options) if mode == "local_template" else draft_local_mock(brief, **options)
        if (research is None and "research" in draft) or (research is not None and draft.get("research") != research):
            raise ValueError("기획 응답이 앱에서 정한 자료 조사를 변경했습니다. 기존 작업은 유지됩니다.")
        with self.lock:
            job = uuid4().hex
            folder = _result_dir(self.base / job, new=True)
            folder.mkdir()
            revision = self._revision(folder, 1)
            revision.mkdir()
            _json_write(folder / "brief.json", draft["brief"])
            _json_write(folder / "creation.json", {"schema_version": 1, "mode": mode,
                                                   "real_execution_allowed": False})
            _json_write(revision / "draft.json", draft)
            self._event(folder, None, "draft", 1)
            return self.view(job)

    def list_jobs(self):
        result = []
        for path in sorted(self.base.iterdir(), key=lambda p: p.name):
            if re.fullmatch(r"[0-9a-f]{32}", path.name):
                try:
                    folder, event = self._load(path.name)
                    brief = validate_brief(self._read(folder, "brief.json"))
                    result.append({"id": path.name, "topic": brief["topic"], "status": event["status"]})
                except (OSError, ValueError, KeyError, TypeError):
                    result.append({"id": path.name, "topic": "검증이 필요한 작업", "status": "blocked"})
        return result

    def view(self, job):
        with self.lock:
            root, event = self._load(job)
            folder, draft = self._current(root, event)
            result = {"id": job, "status": event["status"], "revision": event["revision"],
                      "sequence": event["sequence"], "draft": draft, "actions": STATUS_ACTIONS[event["status"]],
                      "real_execution_allowed": False, "error": event["error"],
                      "quote": None, "prompts": None, "inspection": None, "review": None,
                      "approval_valid_now": False, "approval_note": "새 견적을 확인하고 별도로 승인하세요.",
                      "files": []}
            if event["status"] not in ("draft", "plan_approved", "blocked"):
                values = self._values(folder)
                result.update(quote=values[4], prompts=values[2])
                approval = folder / "approval.json"
                if approval.exists():
                    try:
                        validate_mock_approval(self._read(folder, "approval.json"), *values)
                        result.update(approval_valid_now=True, approval_note="현재 입력의 모의 승인이 유효합니다.")
                    except ValueError:
                        result["approval_note"] = "모의 승인이 만료되거나 달라졌습니다. 새 작업에서 다시 승인하세요."
            if event["status"] in ("result_pending", "changes_requested", "accepted"):
                result["inspection"] = self._read(folder, "inspection.json")
                result["files"] = [name for name in ("video.mp4", "subtitles.srt", "scenes.json", "quality.json", "manifest.json")]
                if event["status"] != "result_pending":
                    result["review"] = self._read(folder, "review.json")
            return result

    def action(self, job, action, payload, sequence):
        with self.lock:
            root, event = self._load(job)
            if type(sequence) is not int or sequence != event["sequence"]:
                raise ValueError("다른 화면에서 작업이 변경됐습니다. 저장된 상태를 다시 불러오세요.")
            if action not in STATUS_ACTIONS[event["status"]]:
                raise ValueError("현재 단계에서는 이 작업을 실행할 수 없습니다. 먼저 별도 승인을 확인하세요.")
            folder, draft = self._current(root, event)
            number, source = event["revision"], event["source"]
            if action == "approve_plan":
                fields(payload, {})
                _json_write(folder / "plan.json", approve_plan(draft))
                status = "plan_approved"
            elif action == "prepare":
                fields(payload, {})
                plan = self._read(folder, "plan.json")
                if source is not None:
                    old = self._source(root, source, number)
                    revision = self._read(folder, "revision.json")
                    prepare_rework_mock(*old, revision, folder / "rework", plan, folder / "prepared")
                else:
                    direction = create_direction(plan)
                    prompts = create_prompts(plan, direction)
                    quote = create_mock_quote(plan, direction, prompts, PRICING)
                    prepared = self._revision(root, number) / "prepared"
                    prepared.mkdir()
                    for name, value in {"plan.json": plan, "direction.json": direction,
                                        "prompts.json": prompts, "pricing.json": PRICING,
                                        "quote.json": quote}.items():
                        _json_write(prepared / name, value)
                status = "prepared"
            elif action == "approve_production":
                fields(payload, {"approved_by", "reason"})
                approval = approve_mock_production(*self._values(folder), **payload)
                _json_write(folder / "approval.json", approval)
                status = "production_approved"
            elif action == "produce":
                fields(payload, {})
                values = self._values(folder)
                approval = self._read(folder, "approval.json")
                validate_mock_approval(approval, *values)
                # All gate checks precede output creation. Failed attempts remain
                # preserved and stop this job rather than silently retrying it.
                try:
                    if source is not None:
                        old = self._source(root, source, number)
                        revision = self._read(folder, "revision.json")
                        produce_rework_mock(*old, revision, folder / "rework", self._read(folder, "plan.json"),
                                            folder / "prepared", approval, folder / "result")
                    else:
                        produce_mock_media(*values, approval, folder / "result")
                    inspected = inspect_mock_result(*values, approval, folder / "result")
                    _json_write(folder / "inspection.json", inspected)
                    status = "result_pending"
                except (OSError, ValueError, RuntimeError) as error:
                    if (folder / "result").exists():
                        self._event(root, event, "blocked", number, source=source,
                                    error="모의 제작이 중단됐습니다. 부분 결과를 보존했습니다. 새 작업에서 다시 확인하세요.")
                    raise ValueError("모의 제작 실패: " + str(error)) from error
            elif action == "review":
                fields(payload, {"schema_version", "reviewer", "decision", "notes", "issues"})
                reviewed = review_mock_result(*self._values(folder), self._read(folder, "approval.json"),
                                              folder / "result", self._read(folder, "inspection.json"), payload)
                _json_write(folder / "review.json", reviewed)
                status = "accepted" if reviewed["status"] == "accepted_mock_result" else "changes_requested"
            elif action in ("revise_draft", "revise_result"):
                fields(payload, {"schema_version", "feedback", "changes"})
                revised = revise_plan(draft, payload) if action == "revise_draft" else None
                new = self._revision(root, number + 1)
                if action == "revise_result":
                    old = (tuple((*self._values(folder), self._read(folder, "approval.json"))),
                           folder / "result", self._read(folder, "inspection.json"), self._read(folder, "review.json"))
                    rework_plan_mock(*old, payload, new / "rework")
                    revised = self._read(new / "rework", "draft.json")
                    source = number
                else:
                    new.mkdir()
                    source = None
                _json_write(new / "draft.json", revised)
                _json_write(new / "revision.json", payload)
                number += 1
                status = "draft"
            self._event(root, event, status, number, source=source)
            return self.view(job)

    def artifact(self, job, revision, name):
        if name not in ("video.mp4", "subtitles.srt", "scenes.json", "quality.json", "manifest.json"):
            raise ValueError("다운로드할 수 없는 파일입니다.")
        root, event = self._load(job)
        if type(revision) is not int or revision != event["revision"] or event["status"] not in (
                "result_pending", "changes_requested", "accepted"):
            raise ValueError("현재 검증된 결과 파일만 열 수 있습니다.")
        self._current(root, event)
        return _file(_result_dir(self._revision(root, revision) / "result"), name)
