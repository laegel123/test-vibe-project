# CLAUDE.md

GitHub PR 작성 시각을 **요일(7) × 시간(0–23) 히트맵 HTML**로 시각화하는 단일 Python3 스크립트.
표준 라이브러리만 사용하므로 `pip install`이나 `gh` CLI가 필요 없다.

---

## 하지 말아야 할 것

1. **외부 의존성 추가 금지.** stdlib만 사용하는 것이 이 프로젝트의 핵심 제약이다. `pip install`이 필요한 패키지를 import하지 말 것.
2. **토큰·시크릿 하드코딩 금지.** GitHub 토큰은 `GITHUB_TOKEN` 환경변수 또는 `--token` 인자로만 전달한다. 코드나 커밋에 절대 포함하지 말 것.
3. **생성물 커밋 금지.** `pr_heatmap.html` 등 `*.html` 출력물은 `.gitignore` 대상이다. 커밋하지 말 것.
4. **단일 파일 구조 임의 분할 금지.** 의도적으로 `pr_heatmap.py` 한 파일로 유지 중이다. 모듈 분리 등 구조 변경은 먼저 사용자와 상의할 것.

---

## 명령어 치트시트

> **빌드: 불필요(인터프리터 스크립트) · 테스트: 미설정 · 린트: 미설정 · 타입체크: 미설정**

```bash
# 실행 — 전체 저장소 모드 (origin 소유자 자동 감지)
python3 pr_heatmap.py

# 특정 사용자 / 단일 저장소 / 타임존
python3 pr_heatmap.py --user laegel123
python3 pr_heatmap.py owner/repo
python3 pr_heatmap.py --tz Asia/Seoul

# 토큰 (rate limit 완화 / private repo)
GITHUB_TOKEN=ghp_xxx python3 pr_heatmap.py

# 출력 경로 + 옵션 조합
python3 pr_heatmap.py owner/repo --state open -o out.html

# 문법 체크 (stdlib만 — 의존성 불필요)
python3 -m py_compile pr_heatmap.py

# 결과 열기 (macOS)
open pr_heatmap.html
```

### 인자

| 인자 | 설명 | 기본값 |
|------|------|--------|
| `repo` | `owner/repo` (단일 저장소 모드). 생략 시 전체 저장소 모드 | 없음 |
| `--user` | 이 사용자가 작성한 모든 저장소의 PR 집계 | origin 소유자 |
| `--limit` | 가져올 최대 PR 개수 (최신순). `0`이면 제한 없음 | `30` |
| `--tz` | 타임존 (예: `Asia/Seoul`, `UTC`) | 시스템 로컬 |
| `--state` | PR 상태 (`all`/`open`/`closed`) | `all` |
| `-o, --output` | 출력 HTML 경로 | `pr_heatmap.html` |
| `--token` | GitHub 토큰 (없으면 `GITHUB_TOKEN` 사용) | — |

---

## 아키텍처 한 눈에

```
test-vibe-project/
├── pr_heatmap.py     # 전체 로직 (단일 진입점)
├── README.md         # 사용법 (한국어)
├── .gitignore        # *.html, *.pyc, __pycache__
└── pr_heatmap.html   # 생성 결과물 (예시)
```

**실행 흐름** (`main` → 위에서 아래로):

```
CLI 파싱(main)
  → repo/owner 감지 (detect_repo / detect_owner, git origin URL 파싱)
  → 타임존 해석 (resolve_tz, zoneinfo)
  → PR 수집
       단일 저장소 모드: fetch_prs       (REST /repos/{o}/{r}/pulls, 100/page 페이지네이션)
       전체 저장소 모드: fetch_authored_prs (Search API, author:로 검색, 최대 1000건)
       (공통 HTTP 처리: _gh_get)
  → UTC created_at → 로컬 TZ 변환 후 7×24 행렬 (build_matrix)
  → 카운트 → GitHub 녹색 그라데이션 (cell_color)
  → 자체 완결형 HTML 렌더 (render_html)
  → 파일 쓰기
```

- **두 모드:** 인자에 `owner/repo`를 주면 단일 저장소 모드(REST), 생략하면 사용자 전체 저장소 모드(Search API).

---

## 코드 컨벤션

- **언어:** Python3 (3.9+ 권장 — `zoneinfo` 필요), 파일 상단에 `from __future__ import annotations`.
- **포매팅:** 4-space 들여쓰기, 큰따옴표(`"`) 문자열.
- **네이밍:** 함수는 `snake_case`, 상수는 `UPPER_CASE`(예: `WEEKDAYS`).
- **타입 힌트:** 모든 함수 시그니처에 현대식 표기(`str | None`, `list[dict]`)로 명시.
- **import:** stdlib만, 모듈 레벨에서. 버전 의존 import는 `try/except`로 폴백(예: `zoneinfo` 없으면 `ZoneInfo = None`).
- **문서/메시지:** docstring은 한국어/영어 혼용, 사용자 대상 출력·에러 메시지는 한국어.
- **에러 처리:** HTTP 상태 코드별(404/401/403) 친절한 메시지 + `sys.exit()`. 네트워크 오류는 `URLError`로 잡아 메시지 출력.

---

## 진행 중인 작업 / 개선 백로그

> 코드상 진행 중인 작업은 없다. 아래는 향후 개선 후보.

- [ ] **테스트 부재** — `build_matrix` / `cell_color` / `detect_repo` 등 순수 함수 단위 테스트 추가 고려.
- [ ] **린트·타입체크 미설정** — 도입 시 도구 선택(ruff/mypy 등)을 사용자와 상의.
- [ ] **전체 모드 1000건 상한** — GitHub Search API 제한. 기간 분할 등으로 더 많은 PR 집계 보완 여지.
- [ ] **미인증 Search API 분당 10요청 제한** — 토큰 권장 안내 강화.
