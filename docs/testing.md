# 테스트

> **현재 상태: 테스트 미작성.** 이 문서는 테스트를 추가할 때 따를 권장 전략과
> 관례를 정의한다. 새 테스트는 여기 기준에 맞춘다.

## 원칙

- **stdlib만 사용.** 프로젝트가 의존성 제로를 유지하므로 테스트도 표준
  라이브러리 `unittest`로 작성한다. (pytest 등 외부 도구 도입은 사용자와 먼저 상의.)
- **네트워크 호출 금지.** 테스트는 실제 GitHub API를 절대 호출하지 않는다.
  HTTP 계층(`urllib`)은 모킹하고, 가능하면 순수 함수만 직접 검증한다.
- **결정적(deterministic)으로.** 실제 시각·타임존·네트워크 상태에 의존하지 않도록
  입력을 고정한다. 시각이 필요하면 명시적 ISO8601 문자열을 인자로 넣는다.

## 무엇을 테스트하나 (우선순위)

순수 함수 → 파싱 로직 → I/O 경계 순으로 가치가 높다.

1. **`build_matrix(prs, tz)`** — 핵심 집계 로직. 최우선.
   - 빈 입력 → 0으로 채운 7×24 행렬, `max_count == 0`.
   - 알려진 `created_at` 묶음 → 기대한 칸에 누적되는지.
   - 타임존 변환: 동일 UTC 시각이 `UTC`와 `Asia/Seoul`에서 다른 칸에 들어가는지.
   - `created_at` 누락/`None`인 PR은 건너뛰는지.
   - `Z` 접미사와 `+00:00` 오프셋을 동일하게 처리하는지.
2. **`cell_color(count, max_count)`** — 경계값 테스트.
   - `count == 0` → `#ebedf0`.
   - 비율 경계(0.25 / 0.5 / 0.75)에서 올바른 단계로 매핑되는지.
   - `max_count == 0`일 때 0 나눗셈 없이 안전한지.
3. **`detect_repo()` / `detect_owner()`** — URL 파싱.
   - SSH(`git@github.com:owner/repo.git`)·HTTPS(`https://github.com/owner/repo.git`)
     형식에서 `owner/repo` 추출.
   - 형식 불일치·git 미설치 시 `None`.
   - `subprocess.check_output`을 모킹해 실제 git 호출 없이 검증.
4. **`fetch_prs` / `fetch_authored_prs`** — 페이지네이션·상한 로직.
   - `urllib.request.urlopen`을 모킹해 페이지를 순차 반환, `limit`/마지막 페이지/
     1000건 상한에서 멈추는지.
   - 404 → 종료 메시지, 401/403 → 종료 메시지 경로 (`sys.exit` 호출 확인).
5. **`render_html(...)`** — 스모크 수준.
   - 반환 문자열에 `<table`, 합계, `total` 값 등 핵심 마커가 포함되는지.
   - 전체 HTML 문자열을 골든 파일로 고정 비교하지 않는다 (스타일 변경에 취약).

## 관례

- **위치/이름:** 테스트는 `tests/` 디렉터리에 두고 파일은 `test_*.py`,
  클래스는 `Test<대상>`, 메서드는 `test_<상황>_<기대>` 형식.
- **실행:** `python3 -m unittest discover -s tests -v`
  (단일 파일은 `python3 -m unittest tests.test_matrix -v`).
- **모킹:** `unittest.mock.patch`로 `pr_heatmap.urlopen`,
  `pr_heatmap.subprocess.check_output` 등 경계만 대체한다. 패치 대상은
  *정의된 모듈*이 아니라 *사용되는 모듈*(`pr_heatmap`) 기준 경로로.
- **`sys.exit` 검증:** 에러 경로는 `with self.assertRaises(SystemExit):`로 확인한다.
- **타임존:** `zoneinfo.ZoneInfo("UTC")`, `ZoneInfo("Asia/Seoul")`처럼 명시적
  타임존을 주입한다. 시스템 로컬 타임존에 의존하는 단언은 피한다.
- **픽스처:** PR 응답은 테스트에 필요한 필드(`created_at`)만 담은 최소 dict로 만든다.
  실제 API 응답 전체를 붙여넣지 않는다.

## 예시 (참고용)

```python
import unittest
from zoneinfo import ZoneInfo
import pr_heatmap


class TestBuildMatrix(unittest.TestCase):
    def test_empty_input_returns_zero_matrix(self):
        matrix, max_count = pr_heatmap.build_matrix([], ZoneInfo("UTC"))
        self.assertEqual(max_count, 0)
        self.assertEqual(len(matrix), 7)
        self.assertEqual(len(matrix[0]), 24)
        self.assertTrue(all(c == 0 for row in matrix for c in row))

    def test_timezone_shifts_bucket(self):
        prs = [{"created_at": "2026-06-10T23:30:00Z"}]  # 수요일 23:30 UTC
        seoul, _ = pr_heatmap.build_matrix(prs, ZoneInfo("Asia/Seoul"))
        # KST = UTC+9 → 목요일 08:30
        self.assertEqual(seoul[3][8], 1)
```

## 향후

- 위 1~3번(순수 함수)부터 시작해 회귀 안전망을 만든 뒤 4~5번(I/O 경계)으로 확장.
- 테스트 도입 시 [CLAUDE.md](../CLAUDE.md)의 "테스트: 미설정" 표기와 실행 명령을
  실제 상태에 맞게 갱신한다.
