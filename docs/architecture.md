# 아키텍처

`pr_heatmap.py` 단일 파일로 구성된 CLI 스크립트다. 외부 의존성 없이 Python
표준 라이브러리만으로 GitHub PR의 작성 시각을 수집·집계·시각화한다.

## 전체 흐름

```
main()
  │
  ├─ argparse로 CLI 인자 파싱
  ├─ resolve_tz(args.tz)              → 타임존 객체
  ├─ token = --token | $GITHUB_TOKEN
  │
  ├─ [단일 저장소 모드]  repo 인자가 있을 때
  │     fetch_prs(repo, state, token, limit)
  │        REST GET /repos/{owner}/{repo}/pulls  (per_page=100, 페이지네이션)
  │
  ├─ [전체 저장소 모드]  repo 인자가 없을 때
  │     user = --user | detect_owner()
  │     fetch_authored_prs(user, token, limit)
  │        Search GET /search/issues?q=author:{user}+type:pr
  │        (sort=created&order=desc, 최대 10페이지 × 100 = 1000건)
  │
  ├─ build_matrix(prs, tz)            → (7×24 행렬, max_count)
  │     created_at(UTC) → 로컬 TZ 변환 → matrix[weekday][hour] += 1
  │
  ├─ render_html(...)                 → 자체 완결형 HTML 문자열
  │     cell_color(count, max_count)  → GitHub 녹색 그라데이션
  │
  └─ 출력 파일 쓰기 (기본 pr_heatmap.html)
```

## 두 가지 동작 모드

| | 단일 저장소 모드 | 전체 저장소 모드 |
|---|---|---|
| 트리거 | `repo`(`owner/repo`) 인자 지정 | `repo` 인자 생략 |
| 대상 | 해당 저장소의 모든 PR | 사용자가 **작성한** 모든 PR (저장소 무관) |
| API | REST `/repos/{o}/{r}/pulls` | Search `/search/issues` |
| 수집 함수 | `fetch_prs` | `fetch_authored_prs` |
| 상한 | 없음 (전체 페이지네이션, `--limit`로 제한) | GitHub Search API 제한으로 최대 1000건 |
| 필터 | `--state`(all/open/closed) | 작성자(`author:`) |

## 모듈 구성

스크립트는 위에서 아래로 "상수 → 유틸 → 수집 → 집계 → 렌더 → main" 순서로 배치된다.

### 감지 / 설정
- **`detect_repo()`** — `git remote get-url origin` 출력을 파싱해 `owner/repo` 추출.
  SSH(`git@github.com:owner/repo.git`)·HTTPS(`https://github.com/owner/repo.git`) 둘 다 지원.
  git이 없거나 형식이 맞지 않으면 `None`.
- **`detect_owner()`** — `detect_repo()` 결과에서 소유자(사용자명)만 분리.
- **`resolve_tz(name)`** — `name`이 있으면 `zoneinfo.ZoneInfo`로 해석, 없으면 시스템 로컬
  타임존. `zoneinfo`가 없는 런타임에서 `--tz`를 주면 안내 후 종료.

### 데이터 수집 (GitHub API)
- **`_gh_get(url, token)`** — GET 공통 처리. 표준 헤더(Accept, User-Agent,
  X-GitHub-Api-Version) 부착, 토큰이 있으면 `Authorization: Bearer`. 404/401/403 및
  네트워크 오류를 사용자 친화 메시지로 변환 후 `sys.exit`.
- **`fetch_prs(repo, state, token, limit)`** — REST PR 목록을 100개 단위로 페이지네이션.
  `limit` 도달·빈 응답·마지막 페이지에서 종료.
- **`fetch_authored_prs(author, token, limit)`** — Search API로 작성자 PR을 최신순 수집.
  Search API 상한(1000건 / 10페이지)을 명시적으로 처리.

### 집계 / 렌더
- **`build_matrix(prs, tz)`** — 각 PR의 `created_at`(UTC ISO8601)을 로컬 TZ로 변환,
  `matrix[weekday][hour]`를 누적. `(matrix, max_count)` 반환. (`weekday()`: 월=0)
- **`cell_color(count, max_count)`** — 비율(0/≤0.25/≤0.5/≤0.75/그 이상)에 따라
  GitHub 컨트리뷰션 스타일 5단계 색상으로 매핑.
- **`render_html(heading, tz_label, matrix, max_count, total)`** — 인라인 CSS를 포함한
  자체 완결형 HTML 테이블 문자열 생성 (시간 헤더, 요일 행, 행/열 합계, 범례).

## 데이터 모델

- **PR 객체**: GitHub API 응답 dict. 이 스크립트는 `created_at` 필드만 사용한다.
- **행렬**: `list[list[int]]`, 크기 7×24. 1번 축 = 요일(월~일), 2번 축 = 시(0~23).

## 설계 원칙

- **의존성 제로** — stdlib만 사용(`argparse`, `json`, `urllib`, `datetime`,
  `zoneinfo`, `subprocess`). 배포·실행이 `python3 pr_heatmap.py` 한 줄이면 충분하도록.
- **자체 완결형 출력** — HTML에 CSS를 인라인으로 포함, 외부 리소스 의존 없음.
- **부수효과는 가장자리에만** — 네트워크/파일 I/O는 수집 함수와 `main`에 모으고,
  `build_matrix`·`cell_color`·`render_html`은 순수 함수로 유지한다.

> 테스트 전략과 관례는 [testing.md](./testing.md) 참고.
