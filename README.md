# PR 작성 시간대 히트맵

GitHub Pull Request 작성 시각을 **요일 × 시간(0–23)** 히트맵으로
시각화하는 도구입니다. "나는 주로 언제 PR을 올리는가?"를 한눈에 보여줍니다.

- Python **표준 라이브러리만** 사용 — `pip install`, `gh` CLI 불필요
- 두 가지 모드: **전체 저장소**(내가 작성한 모든 PR) / **단일 저장소**
- 작성 시각을 **로컬 타임존**(또는 지정한 타임존)으로 변환
- 의존성 없는 **자체 완결형 HTML** 출력 (GitHub 잔디 스타일 색상)

## 사용법

### 전체 저장소 모드 (기본)

내가 작성한 PR을 **모든 저장소에서** 모아 집계합니다 (GitHub Search API).

```bash
# origin 소유자를 사용자로 자동 감지
python3 pr_heatmap.py

# 사용자 직접 지정
python3 pr_heatmap.py --user laegel123

# 타임존 지정 (기본: 시스템 로컬 시간)
python3 pr_heatmap.py --tz Asia/Seoul

# 토큰 설정 (검색 API 레이트리밋 완화 + 비공개 저장소 포함)
GITHUB_TOKEN=ghp_xxxxx python3 pr_heatmap.py
```

### 단일 저장소 모드

특정 저장소의 모든 PR(작성자 무관)을 집계합니다.

```bash
python3 pr_heatmap.py owner/repo
python3 pr_heatmap.py owner/repo --state open --tz Asia/Seoul
```

생성된 `pr_heatmap.html`을 브라우저에서 열면 됩니다.

```bash
open pr_heatmap.html   # macOS
```

## 옵션

| 옵션 | 설명 | 기본값 |
|------|------|--------|
| `repo` | `owner/repo` 지정 시 **단일 저장소 모드** | (없음 → 전체 저장소 모드) |
| `--user` | 전체 저장소 모드에서 집계할 작성자 | origin 소유자 |
| `--tz` | 타임존 (예: `Asia/Seoul`, `UTC`) | 시스템 로컬 |
| `--state` | 단일 저장소 모드의 PR 상태 (`all`/`open`/`closed`) | `all` |
| `-o, --output` | 출력 HTML 경로 | `pr_heatmap.html` |
| `--token` | GitHub 토큰 (없으면 `GITHUB_TOKEN` 사용) | — |

## 참고

- 인증 없이도 동작하지만 레이트리밋이 빡빡합니다 (검색 API 미인증 분당 10회).
  PR이 많거나 비공개 저장소를 포함하려면 `GITHUB_TOKEN`을 설정하세요.
- 전체 저장소 모드는 GitHub Search API 특성상 **최대 1000개 PR**까지 집계됩니다.
- 히트맵 칸 색이 진할수록 해당 요일·시간대에 PR을 많이 올렸다는 의미입니다.
