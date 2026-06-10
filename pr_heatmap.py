#!/usr/bin/env python3
"""GitHub PR 작성 시간대 히트맵 생성기.

GitHub REST API로 저장소의 PR을 모두 가져와 작성 시각(created_at)을
'요일 × 시간(0-23)' 히트맵으로 시각화한 자체 완결형 HTML을 생성한다.

표준 라이브러리만 사용하므로 별도 설치(pip, gh CLI)가 필요 없다.

사용 예:
    python3 pr_heatmap.py                      # origin 원격에서 자동 감지
    python3 pr_heatmap.py owner/repo
    python3 pr_heatmap.py --tz Asia/Seoul
    GITHUB_TOKEN=ghp_xxx python3 pr_heatmap.py  # 비공개 저장소/레이트리밋 완화
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except ImportError:  # pragma: no cover
    ZoneInfo = None

WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]


def detect_repo() -> str | None:
    """origin 원격 URL에서 'owner/repo'를 추출한다."""
    try:
        url = subprocess.check_output(
            ["git", "remote", "get-url", "origin"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None

    # git@github.com:owner/repo.git  또는  https://github.com/owner/repo.git
    if url.startswith("git@"):
        path = url.split(":", 1)[-1]
    else:
        path = url.split("github.com/", 1)[-1]
    path = path.removesuffix(".git").strip("/")
    return path if path.count("/") == 1 else None


def detect_owner() -> str | None:
    """origin 원격에서 소유자(사용자명)만 추출한다."""
    repo = detect_repo()
    return repo.split("/", 1)[0] if repo else None


def resolve_tz(name: str | None):
    """타임존 객체를 돌려준다. name이 없으면 시스템 로컬 타임존."""
    if not name:
        # 시스템 로컬 타임존 (datetime.astimezone() 기본값과 동일)
        return datetime.now().astimezone().tzinfo
    if ZoneInfo is None:
        sys.exit("이 Python에는 zoneinfo가 없습니다. --tz를 빼고 로컬 시간으로 실행하세요.")
    try:
        return ZoneInfo(name)
    except Exception:
        sys.exit(f"알 수 없는 타임존: {name!r} (예: Asia/Seoul, UTC, America/New_York)")


def fetch_prs(repo: str, state: str, token: str | None, limit: int | None = None) -> list[dict]:
    """PR을 페이지네이션으로 가져온다. limit이 있으면 그만큼만."""
    prs: list[dict] = []
    page = 1
    while True:
        url = (
            f"https://api.github.com/repos/{repo}/pulls"
            f"?state={state}&per_page=100&page={page}"
        )
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "pr-heatmap",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"

        req = Request(url, headers=headers)
        try:
            with urlopen(req) as resp:
                batch = json.load(resp)
        except HTTPError as e:
            if e.code == 404:
                sys.exit(f"저장소를 찾을 수 없습니다: {repo} (비공개라면 GITHUB_TOKEN 필요)")
            if e.code in (401, 403):
                detail = e.read().decode("utf-8", "replace")[:200]
                sys.exit(f"접근 거부({e.code}). 토큰/레이트리밋을 확인하세요.\n{detail}")
            raise
        except URLError as e:
            sys.exit(f"네트워크 오류: {e.reason}")

        if not batch:
            break
        prs.extend(batch)
        if limit is not None and len(prs) >= limit:
            break
        if len(batch) < 100:
            break
        page += 1
        print(f"  ...{len(prs)}개 수집", file=sys.stderr)
    return prs[:limit] if limit is not None else prs


def _gh_get(url: str, token: str | None) -> dict | list:
    """GitHub API GET 공통 처리."""
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "pr-heatmap",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = Request(url, headers=headers)
    try:
        with urlopen(req) as resp:
            return json.load(resp)
    except HTTPError as e:
        if e.code == 404:
            sys.exit("리소스를 찾을 수 없습니다 (비공개라면 GITHUB_TOKEN 필요)")
        if e.code in (401, 403):
            detail = e.read().decode("utf-8", "replace")[:200]
            sys.exit(f"접근 거부({e.code}). 토큰/레이트리밋을 확인하세요.\n{detail}")
        raise
    except URLError as e:
        sys.exit(f"네트워크 오류: {e.reason}")


def fetch_authored_prs(author: str, token: str | None, limit: int | None = None) -> list[dict]:
    """Search API로 author가 작성한 PR을 최신순으로 수집한다.

    limit이 있으면 가장 최근 limit개까지만. 검색 API는 최대 1000건까지 반환한다.
    """
    from urllib.parse import quote

    per_page = min(limit, 100) if limit is not None else 100
    prs: list[dict] = []
    page = 1
    while page <= 10:  # 검색 API 상한
        q = quote(f"author:{author} type:pr")
        url = (
            f"https://api.github.com/search/issues"
            f"?q={q}&per_page={per_page}&page={page}&sort=created&order=desc"
        )
        data = _gh_get(url, token)
        items = data.get("items", []) if isinstance(data, dict) else []
        total = data.get("total_count", 0) if isinstance(data, dict) else 0
        if not items:
            break
        prs.extend(items)
        if limit is not None and len(prs) >= limit:
            break
        print(f"  ...{len(prs)}/{min(total, 1000)}개 수집", file=sys.stderr)
        if len(prs) >= min(total, 1000) or len(items) < per_page:
            break
        page += 1
    return prs[:limit] if limit is not None else prs


def build_matrix(prs: list[dict], tz) -> tuple[list[list[int]], int]:
    """7(요일) x 24(시간) 카운트 행렬을 만든다. (matrix, max_count) 반환."""
    matrix = [[0] * 24 for _ in range(7)]
    for pr in prs:
        created = pr.get("created_at")
        if not created:
            continue
        dt_utc = datetime.fromisoformat(created.replace("Z", "+00:00"))
        if dt_utc.tzinfo is None:
            dt_utc = dt_utc.replace(tzinfo=timezone.utc)
        local = dt_utc.astimezone(tz)
        matrix[local.weekday()][local.hour] += 1
    max_count = max((max(row) for row in matrix), default=0)
    return matrix, max_count


def cell_color(count: int, max_count: int) -> str:
    """카운트를 GitHub 스타일 녹색 그라데이션으로 매핑한다."""
    if count == 0:
        return "#ebedf0"
    ratio = count / max_count if max_count else 0
    # 옅은 녹색 -> 진한 녹색 4단계
    if ratio <= 0.25:
        return "#9be9a8"
    if ratio <= 0.5:
        return "#40c463"
    if ratio <= 0.75:
        return "#30a14e"
    return "#216e39"


def render_html(heading: str, tz_label: str, matrix, max_count: int, total: int) -> str:
    rows_html = []
    for d, row in enumerate(matrix):
        cells = []
        for h, count in enumerate(row):
            color = cell_color(count, max_count)
            title = f"{WEEKDAYS[d]}요일 {h:02d}시 — PR {count}개"
            cells.append(
                f'<td class="cell" style="background:{color}" title="{title}"></td>'
            )
        day_total = sum(row)
        rows_html.append(
            f'<tr><th class="day">{WEEKDAYS[d]}</th>{"".join(cells)}'
            f'<td class="rowtotal">{day_total}</td></tr>'
        )

    hour_headers = "".join(f'<th class="hour">{h}</th>' for h in range(24))
    col_totals = "".join(
        f'<td class="coltotal">{sum(matrix[d][h] for d in range(7))}</td>'
        for h in range(24)
    )

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{heading} — PR 작성 시간대 히트맵</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    margin: 2.5rem; color: #1f2328; background: #fff;
  }}
  h1 {{ font-size: 1.4rem; margin: 0 0 .25rem; }}
  .meta {{ color: #656d76; font-size: .9rem; margin-bottom: 1.5rem; }}
  .meta strong {{ color: #1f2328; }}
  table {{ border-collapse: collapse; }}
  th, td {{ text-align: center; font-size: .72rem; color: #656d76; }}
  th.hour {{ width: 22px; font-weight: 400; padding-bottom: 4px; }}
  th.day {{ width: 28px; padding-right: 8px; font-weight: 600; color: #1f2328; }}
  td.cell {{
    width: 20px; height: 20px; border-radius: 3px;
    border: 1px solid rgba(27,31,36,.06);
  }}
  td.rowtotal, td.coltotal {{ font-variant-numeric: tabular-nums; color: #1f2328; }}
  td.rowtotal {{ padding-left: 10px; font-weight: 600; }}
  td.coltotal {{ padding-top: 6px; font-size: .65rem; color: #8c959f; }}
  .corner {{ }}
  .legend {{
    display: flex; align-items: center; gap: 6px;
    margin-top: 1.5rem; font-size: .78rem; color: #656d76;
  }}
  .legend .swatch {{
    width: 18px; height: 18px; border-radius: 3px;
    border: 1px solid rgba(27,31,36,.06);
  }}
</style>
</head>
<body>
  <h1>{heading}</h1>
  <p class="meta">
    PR 작성 시간대 히트맵 &middot; 총 <strong>{total}</strong>개 PR &middot;
    타임존 <strong>{tz_label}</strong> &middot; 최대 <strong>{max_count}</strong>개/칸
  </p>
  <table>
    <tr><th class="corner"></th>{hour_headers}<th></th></tr>
    {"".join(rows_html)}
    <tr><th></th>{col_totals}<td></td></tr>
  </table>
  <div class="legend">
    <span>적음</span>
    <span class="swatch" style="background:#ebedf0"></span>
    <span class="swatch" style="background:#9be9a8"></span>
    <span class="swatch" style="background:#40c463"></span>
    <span class="swatch" style="background:#30a14e"></span>
    <span class="swatch" style="background:#216e39"></span>
    <span>많음</span>
  </div>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="GitHub PR 작성 시간대 히트맵 HTML 생성기"
    )
    parser.add_argument(
        "repo",
        nargs="?",
        help="owner/repo (단일 저장소 모드). 생략 시 --user 기준 전체 저장소 모드",
    )
    parser.add_argument(
        "--user",
        help="이 사용자가 작성한 모든 저장소의 PR을 집계 (생략 시 origin 소유자)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=30,
        help="가져올 최대 PR 개수 (최신순, 기본 30). 0이면 제한 없음",
    )
    parser.add_argument(
        "--tz", help="타임존 (예: Asia/Seoul, UTC). 생략 시 시스템 로컬 시간"
    )
    parser.add_argument(
        "--state",
        default="all",
        choices=["all", "open", "closed"],
        help="가져올 PR 상태 (기본 all)",
    )
    parser.add_argument(
        "-o", "--output", default="pr_heatmap.html", help="출력 HTML 경로"
    )
    parser.add_argument(
        "--token", help="GitHub 토큰 (없으면 GITHUB_TOKEN 환경변수 사용)"
    )
    args = parser.parse_args()

    tz = resolve_tz(args.tz)
    tz_label = args.tz or str(tz) or "local"
    token = args.token or os.environ.get("GITHUB_TOKEN")

    limit = args.limit if args.limit and args.limit > 0 else None

    if args.repo:
        # 단일 저장소 모드
        repo = args.repo
        print(f"PR 수집 중: {repo} (state={args.state})...", file=sys.stderr)
        prs = fetch_prs(repo, args.state, token, limit)
        heading = repo
    else:
        # 전체 저장소 모드 — 사용자가 작성한 모든 PR 집계
        user = args.user or detect_owner()
        if not user:
            sys.exit(
                "사용자를 알 수 없습니다. --user 사용자명 을 지정하거나 "
                "owner/repo 를 인자로 주세요."
            )
        if not token:
            print(
                "  ⚠ 토큰 없이 실행 중 — 검색 API는 미인증 시 분당 10회로 제한됩니다. "
                "PR이 많으면 GITHUB_TOKEN 설정을 권장합니다.",
                file=sys.stderr,
            )
        print(f"PR 수집 중: 사용자 {user} 의 전체 저장소...", file=sys.stderr)
        prs = fetch_authored_prs(user, token, limit)
        heading = f"{user} · 전체 저장소"

    print(f"총 {len(prs)}개 PR 수집 완료.", file=sys.stderr)

    matrix, max_count = build_matrix(prs, tz)
    html = render_html(heading, tz_label, matrix, max_count, len(prs))

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"히트맵 생성 완료 → {args.output}")


if __name__ == "__main__":
    main()
