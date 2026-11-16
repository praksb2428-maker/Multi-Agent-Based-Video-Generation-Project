"""Command-line entry point for the content-planning milestone."""

import argparse
import json
from pathlib import Path

from src.shorts import approve_plan, create_draft, revise_plan


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError("non-finite JSON number")


def _read_json(path):
    with Path(path).open(encoding="utf-8") as stream:
        return json.load(stream, object_pairs_hook=_unique_object, parse_constant=_reject_constant)


def _write_json(path, value):
    target = Path(path)
    if target.exists():
        raise ValueError(f"output already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description="숏츠 콘텐츠 기획 초안 및 승인")
    subcommands = parser.add_subparsers(dest="command", required=True)
    for name in ("draft", "draft-mock", "draft-local", "approve", "direct"):
        command = subcommands.add_parser(name)
        command.add_argument("input", help="입력 JSON 경로")
        command.add_argument("output", help="새로 만들 출력 JSON 경로")
        if name == "draft-mock":
            command.add_argument("--mock-response", help="선택적 합성 SDK 응답 JSON 경로(외부 호출 없음)")
    revision = subcommands.add_parser("revise", help="명시적 수정 JSON 반영 후 재승인할 초안 저장")
    revision.add_argument("input", help="기존 기획 JSON 경로")
    revision.add_argument("request", help="수정 요청 JSON 경로")
    revision.add_argument("output", help="새로 만들 수정 기획 JSON 경로")
    prompts = subcommands.add_parser("prompts", help="승인 기획과 로컬 연출에서 범용 프롬프트 저장")
    prompts.add_argument("input", help="승인된 기획 JSON 경로")
    prompts.add_argument("direction", help="로컬 연출 JSON 경로")
    prompts.add_argument("output", help="새로 만들 프롬프트 JSON 경로")
    for name in ("quote-mock", "approve-production-mock", "check-production-mock"):
        command = subcommands.add_parser(name, help="가상 단위 견적·승인 확인 전용, 실제 제작 없음")
        command.add_argument("input", help="승인 기획 JSON")
        command.add_argument("direction", help="연출 JSON")
        command.add_argument("prompts", help="프롬프트 JSON")
        command.add_argument("pricing", help="합성 mock_credit 단가 JSON")
        if name != "quote-mock":
            command.add_argument("quote", help="모의 견적 JSON")
        if name == "approve-production-mock":
            command.add_argument("--approved-by", required=True, help="모의 호출자 표기, 신원 인증 아님")
            command.add_argument("--reason", required=True, help="모의 확인 사유")
        if name == "check-production-mock":
            command.add_argument("approval", help="저장된 모의 승인 JSON")
        else:
            command.add_argument("output", help="새로 만들 모의 결과 JSON")
    for name in ("produce-mock", "validate-result-mock"):
        command = subcommands.add_parser(name, help="로컬 합성 영상 전용, 실제 AI·유료 제작 없음")
        for field in ("input", "direction", "prompts", "pricing", "quote", "approval"):
            command.add_argument(field, help="현재 모의 제작 입력 JSON")
        command.add_argument("result", help="프로젝트 workspace 아래 결과 폴더(제작 시 새 경로)")
    for name in ("inspect-result-mock", "review-result-mock", "check-result-review-mock"):
        command = subcommands.add_parser(name, help="합성 결과의 검사·명시적 확인·수정 요청 기록, 자동 실행 없음")
        for field in ("input", "direction", "prompts", "pricing", "quote", "approval"):
            command.add_argument(field, help="현재 모의 제작 입력 JSON")
        command.add_argument("result", help="프로젝트 workspace 아래 보존된 결과 폴더")
        if name != "inspect-result-mock":
            command.add_argument("inspection", help="이 결과의 모의 검사 보고서 JSON")
        if name == "review-result-mock":
            command.add_argument("request", help="명시적 확인·수정 요청 JSON")
        if name == "check-result-review-mock":
            command.add_argument("review", help="재검증할 확인 기록 JSON")
        else:
            command.add_argument("output", help="새로 저장할 보고·확인 JSON")
    for name in ("rework-plan-mock", "prepare-rework-mock", "produce-rework-mock"):
        command = subcommands.add_parser(name, help="명시적 수정·별도 재승인·로컬 모의 재제작")
        for field in ("input", "direction", "prompts", "pricing", "quote", "approval"):
            command.add_argument(field, help="보존된 원본 제작 입력 JSON")
        for field in ("result", "inspection", "review", "revision"):
            command.add_argument(field, help="현재 원본 결과·검사·수정 확인·명시적 교체 JSON")
        if name != "rework-plan-mock":
            command.add_argument("rework", help="미승인 수정 초안 bundle 폴더")
            command.add_argument("approved", help="별도로 재승인한 정확한 수정 기획")
        if name == "produce-rework-mock":
            command.add_argument("prepared", help="새 견적 bundle 폴더")
            command.add_argument("new_approval", help="새 견적의 별도 모의 제작 승인 JSON")
        command.add_argument("output", help="프로젝트 workspace 아래 새 출력 폴더")
    args = parser.parse_args(argv)
    try:
        data = _read_json(args.input)
        if args.command in ("rework-plan-mock", "prepare-rework-mock", "produce-rework-mock"):
            from src.mock_rework import rework_plan_mock, prepare_rework_mock, produce_rework_mock
            values = (data, *(_read_json(path) for path in
                             (args.direction, args.prompts, args.pricing, args.quote, args.approval)))
            common = (values, args.result, _read_json(args.inspection), _read_json(args.review),
                      _read_json(args.revision))
            if args.command == "rework-plan-mock":
                result = rework_plan_mock(*common, args.output)
            elif args.command == "prepare-rework-mock":
                result = prepare_rework_mock(*common, args.rework, _read_json(args.approved), args.output)
            else:
                result = produce_rework_mock(*common, args.rework, _read_json(args.approved),
                                            args.prepared, _read_json(args.new_approval), args.output)
            print(json.dumps(result, ensure_ascii=False, allow_nan=False))
            return 0
        elif args.command in ("inspect-result-mock", "review-result-mock", "check-result-review-mock"):
            from src.quality_feedback import inspect_mock_result, review_mock_result, validate_mock_review
            values = (data, *(_read_json(path) for path in
                             (args.direction, args.prompts, args.pricing, args.quote, args.approval)))
            if args.command == "inspect-result-mock":
                result = inspect_mock_result(*values, args.result)
                _write_json(args.output, result)
                print(args.output)
                return 0 if result["status"] == "technical_pass" else 2
            inspection = _read_json(args.inspection)
            if args.command == "check-result-review-mock":
                result = validate_mock_review(_read_json(args.review), *values, args.result, inspection)
                print(json.dumps({"status": result["status"], "record_valid": True,
                                  "real_execution_allowed": False}, ensure_ascii=False))
                return 0
            result = review_mock_result(*values, args.result, inspection, _read_json(args.request))
        elif args.command in ("produce-mock", "validate-result-mock"):
            from src.mock_media import produce_mock_media, validate_mock_result
            values = (data, *(_read_json(path) for path in
                             (args.direction, args.prompts, args.pricing, args.quote, args.approval)))
            operation = produce_mock_media if args.command == "produce-mock" else validate_mock_result
            result = operation(*values, args.result)
            print(json.dumps(result, ensure_ascii=False, allow_nan=False))
            return 0
        elif args.command in ("quote-mock", "approve-production-mock", "check-production-mock"):
            from src.mock_production import create_mock_quote, approve_mock_production, validate_mock_approval
            direction, prompts, pricing = (_read_json(path) for path in
                                           (args.direction, args.prompts, args.pricing))
            if args.command == "quote-mock":
                result = create_mock_quote(data, direction, prompts, pricing)
            elif args.command == "approve-production-mock":
                result = approve_mock_production(data, direction, prompts, pricing, _read_json(args.quote),
                                                approved_by=args.approved_by, reason=args.reason)
            else:
                validate_mock_approval(_read_json(args.approval), data, direction, prompts, pricing,
                                       _read_json(args.quote))
                print("mock approval valid; real execution is NOT authorized")
                return 0
        elif args.command == "direct":
            from src.direction import create_direction
            result = create_direction(data)
        elif args.command == "prompts":
            from src.direction import create_prompts
            result = create_prompts(data, _read_json(args.direction))
        elif args.command == "revise":
            result = revise_plan(data, _read_json(args.request))
        elif args.command == "draft-mock":
            from src.openai_mock import create_mock_draft
            if args.mock_response:
                result = create_mock_draft(data, response_body=_read_json(args.mock_response))
            else:
                result = create_mock_draft(data)
        elif args.command == "draft-local":
            # Reject an existing output before spending any local inference.
            if Path(args.output).exists():
                raise ValueError(f"output already exists: {args.output}")
            from src.local_ollama import create_local_draft
            result = create_local_draft(data)
        else:
            result = create_draft(data) if args.command == "draft" else approve_plan(data)
        _write_json(args.output, result)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        parser.exit(2, f"오류: {error}\n")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
