"""
离线生成词表内「形近词」邻接关系。

从 JSONL 格式的 ``words.jsonl``（每行一个 {"word","content"}）读取词条，结合长度窗口过滤、
字符 multiset 的 Dice 筛选与（有上界的）编辑距离打分，写出 JSON **数组**（与输入行序一一对应，
重复的 ``word`` 字符串不会合并）：

  [ {"word": "<词条>", "neighbors": ["...", ...]}, ... ]

词表更新后重新运行本脚本即可；应用侧可直接加载输出文件，无需在背诵时实时算邻居。

全大写字母缩写（如 AM、PM、HIV）不参与形近词计算，也不会作为他人的形近词输出。

词条中第一个英文字母为大写者（如 Africa、Alaska，含专有名词式书写）同样不参与形近词计算，
也不可出现在他人的 neighbors 中。

筛出的 neighbors 会再按「首部连续相同字母数」分级排序（首 3 字一致最前，首字即不同最后）。

可选：执行 ``pip install rapidfuzz``，在大词表上显著加快编辑距离计算。
"""

from __future__ import annotations

import argparse
import heapq
import json
from collections import Counter
from pathlib import Path

try:
    from rapidfuzz.distance import Levenshtein as _RfLevenshtein  # type: ignore[import-not-found]

    def _rf_bounded_distance(a: str, b: str, max_dist: int) -> int | None:
        d = _RfLevenshtein.distance(a, b, score_cutoff=max_dist)
        if d > max_dist:
            return None
        return int(d)

except ImportError:
    _rf_bounded_distance = None  # type: ignore[misc, assignment]


def _default_words_path() -> Path:
    return Path(__file__).resolve().parent / "words.jsonl"


def _default_output_path() -> Path:
    return Path(__file__).resolve().parent / "similar_shape_words.json"


def load_word_entries(path: Path) -> list[str]:
    raw = path.read_text(encoding="utf-8").strip()
    if path.suffix.lower() == ".json" and raw.startswith("["):
        try:
            arr = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ValueError(f"{path}: invalid JSON array") from e
        if not isinstance(arr, list):
            raise ValueError(f"{path}: JSON root must be an array")
        words: list[str] = []
        for item in arr:
            if not isinstance(item, dict):
                continue
            w = item.get("word")
            if isinstance(w, str) and w.strip():
                words.append(w.strip())
        return words

    words = []
    with path.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(f"{path}: line {line_no}: invalid JSON") from e
            w = obj.get("word")
            if not isinstance(w, str) or not w.strip():
                continue
            words.append(w.strip())
    return words


def write_similar_neighbors_json(
    words: list[str],
    output: Path,
    *,
    top_k: int = 10,
    dice_min: float = 0.52,
    heap_cap_mult: int = 24,
) -> int:
    """写入形近词邻接 JSON 数组，返回至少有一个邻居的词条数。"""
    neighbor_lists = build_similar_neighbors(
        words,
        top_k=top_k,
        dice_min=dice_min,
        heap_cap_mult=heap_cap_mult,
    )
    payload = [
        {"word": words[i], "neighbors": neighbor_lists[i]}
        for i in range(len(words))
    ]
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return sum(1 for row in neighbor_lists if row)


def build_similar_index_for_path(
    input_path: Path,
    output_path: Path | None = None,
    *,
    top_k: int = 10,
    dice_min: float = 0.52,
    heap_cap_mult: int = 24,
) -> Path:
    """从词书 JSON/JSONL 生成形近词索引文件。"""
    words = load_word_entries(input_path)
    if not words:
        raise ValueError(f"No words loaded from {input_path}")
    out = output_path or input_path.with_name(
        input_path.stem.replace("_edited", "") + "_similar_shape_words.json"
        if "_edited" in input_path.stem
        else input_path.stem + "_similar_shape_words.json"
    )
    write_similar_neighbors_json(
        words,
        out,
        top_k=top_k,
        dice_min=dice_min,
        heap_cap_mult=heap_cap_mult,
    )
    return out


def _max_edit_distance(word_len: int) -> int:
    """Keep short words tight (fewer false positives); allow more drift for longer spellings."""
    if word_len <= 4:
        return 1
    if word_len <= 7:
        return 3
    return 4


def _length_gap_for(word_len: int) -> int:
    if word_len <= 6:
        return 2
    return 3


def _is_uppercase_abbreviation(word: str) -> bool:
    """
    全大写字母缩写（如 AM、PM、HIV）：不参与形近词计算，也不作为他人的形近词出现。
    仅依据词条原始字符串中的字母：至少两个字母，且均为 uppercase。
    """
    letters = [c for c in word if c.isalpha()]
    if len(letters) < 2:
        return False
    return all(c.isupper() for c in letters)


def _is_leading_uppercase_word(word: str) -> bool:
    """
    首字母（首个英文字母）为大写的词条：不参与形近词，也不作为他人的形近词。
    跳过词条前的非字母符号（如连字符、引号），只看第一个 isalpha() 字符。
    """
    for c in word:
        if c.isalpha():
            return c.isupper()
    return False


def _skip_similar_shape(word: str) -> bool:
    """全大写缩写或首字母大写词条均排除在形近词体系之外。"""
    return _is_uppercase_abbreviation(word) or _is_leading_uppercase_word(word)


def _dice_precount(ca: Counter, cb: Counter, la: int, lb: int) -> float:
    """Sørensen–Dice on multiset intersection using precomputed Counter objects."""
    if la == 0 or lb == 0:
        return 0.0
    if len(ca) > len(cb):
        ca, cb = cb, ca
    inter = 0
    for ch, va in ca.items():
        vb = cb.get(ch)
        if vb:
            inter += min(va, vb)
    return (2.0 * inter) / (la + lb)


def levenshtein_bounded(a: str, b: str, max_dist: int) -> int | None:
    """
    Levenshtein distance; returns None early if distance exceeds max_dist.
    Uses two-row DP with column-wise cutoff.
    """
    la, lb = len(a), len(b)
    if la == 0:
        return lb if lb <= max_dist else None
    if lb == 0:
        return la if la <= max_dist else None
    if abs(la - lb) > max_dist:
        return None

    prev = list(range(lb + 1))
    curr = [0] * (lb + 1)

    for i in range(1, la + 1):
        curr[0] = i
        row_min = curr[0]
        ai = a[i - 1]
        for j in range(1, lb + 1):
            cost = 0 if ai == b[j - 1] else 1
            curr[j] = min(
                prev[j] + 1,
                curr[j - 1] + 1,
                prev[j - 1] + cost,
            )
            if curr[j] < row_min:
                row_min = curr[j]
        if row_min > max_dist:
            return None
        prev, curr = curr, prev

    dist = prev[lb]
    return dist if dist <= max_dist else None


def bounded_edit_distance(a: str, b: str, max_dist: int) -> int | None:
    """Prefer rapidfuzz when installed; otherwise pure-Python bounded DP."""
    if _rf_bounded_distance is not None:
        return _rf_bounded_distance(a, b, max_dist)
    return levenshtein_bounded(a, b, max_dist)


def _push_capped(heap: list[tuple[int, int]], item: tuple[int, int], cap: int) -> None:
    """Keep only `cap` pairs with smallest edit distance (tie-break by index later)."""
    dist, j = item
    heapq.heappush(heap, (-dist, j))
    if len(heap) > cap:
        heapq.heappop(heap)


def _common_prefix_length(a: str, b: str) -> int:
    """Two strings compared left to right (already casefolded)."""
    n = min(len(a), len(b))
    k = 0
    while k < n and a[k] == b[k]:
        k += 1
    return k


def _prefix_shape_level(source_cf: str, neighbor_cf: str) -> int:
    """
    形近词前缀分级（用于 neighbors 排序，数值越大越靠前）：
    level 4 — 首字母起至少连续 3 个字符相同；
    level 3 — 恰好连续 2 个首字符相同；
    level 2 — 仅首字符相同；
    level 1 — 首字符即不同。
    """
    cp = _common_prefix_length(source_cf, neighbor_cf)
    if cp >= 3:
        return 4
    if cp == 2:
        return 3
    if cp == 1:
        return 2
    return 1


def _sort_neighbors_by_prefix_level(
    source_cf: str,
    picked: list[tuple[int, str]],
) -> list[str]:
    """同一批候选内：level 高者优先；同级保持编辑距离优先，再按拼写字母序。"""
    picked.sort(
        key=lambda t: (-_prefix_shape_level(source_cf, t[1].casefold()), t[0], t[1].casefold())
    )
    return [w for _, w in picked]


def build_similar_neighbors(
    words: list[str],
    *,
    top_k: int = 6,
    dice_min: float = 0.8,
    heap_cap_mult: int = 24,
) -> list[list[str]]:
    """
    对每个词，在其余词条中按编辑距离取出至多 ``top_k`` 个最近邻（距离比较时不区分大小写；
    邻居列表保留词表中的原始大小写）。

    词对按长度排序后枚举，仅比较满足 i<j 且长度差不超过允许区间的索引对（离线批处理思路）。
    字符 multiset 的 Dice 系数使用每个词预先算好的 Counter，避免逐对新建 Counter；
    每个词用带容量上限的堆保存候选对，以控制内存占用。

    全大写字母缩写（如 AM、PM、HIV）以及首英文字母大写的词条（如 Africa、Alaska）
    既不查询形近词，也不会出现在其他词的邻居列表中。

    输出顺序：在编辑距离筛出的候选上，再按前缀重合分级（首 3 / 首 2 / 首 1 / 首字符不同）
    从高到低排列；同级仍优先编辑距离更近者。
    """
    lowers = [w.casefold() for w in words]
    n = len(words)
    skip_shape = [_skip_similar_shape(w) for w in words]
    counts = [Counter(s) for s in lowers]
    lens = [len(s) for s in lowers]

    cap = max(heap_cap_mult * top_k, max(48, top_k * 4))

    # Sort by length then spelling so inner loops can stop once length grows too far.
    order = sorted(range(n), key=lambda i: (lens[i], lowers[i]))

    heaps: list[list[tuple[int, int]]] = [[] for _ in range(n)]

    for pos_i in range(n):
        i = order[pos_i]
        if skip_shape[i]:
            continue
        lw = lowers[i]
        li = lens[i]
        max_ed_i = _max_edit_distance(li)
        gap_i = _length_gap_for(li)
        ci = counts[i]

        for pos_j in range(pos_i + 1, n):
            j = order[pos_j]
            if skip_shape[j]:
                continue
            lj = lens[j]
            if lj - li > gap_i:
                break

            other = lowers[j]
            if other == lw:
                continue

            max_ed = min(max_ed_i, _max_edit_distance(lj))
            if max_ed < 1:
                continue

            if lj - li > max_ed:
                continue

            if _dice_precount(ci, counts[j], li, lj) < dice_min:
                continue

            dist = bounded_edit_distance(lw, other, max_ed)
            if dist is None or dist < 1:
                continue

            _push_capped(heaps[i], (dist, j), cap)
            _push_capped(heaps[j], (dist, i), cap)

    out_rows: list[list[str]] = []
    for i in range(n):
        raw_pairs = [(-neg_d, j) for neg_d, j in heaps[i]]
        raw_pairs.sort(key=lambda t: (t[0], words[t[1]].casefold()))
        seen: set[str] = set()
        picked: list[tuple[int, str]] = []
        for dist, j in raw_pairs:
            raw = words[j]
            key = raw.casefold()
            if key == lowers[i]:
                continue
            if key in seen:
                continue
            seen.add(key)
            picked.append((dist, raw))
            if len(picked) >= top_k:
                break
        ordered = _sort_neighbors_by_prefix_level(lowers[i], picked)
        out_rows.append(ordered)

    return out_rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build similar-shape word neighbors from words.jsonl (JSONL)."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=_default_words_path(),
        help="Path to words.jsonl (JSONL with word/content fields).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=_default_output_path(),
        help="Where to write the neighbor map JSON.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=10,
        metavar="K",
        help="Maximum neighbors stored per word (default: 10).",
    )
    parser.add_argument(
        "--dice-min",
        type=float,
        default=0.52,
        metavar="X",
        help="Minimum multiset Dice coefficient before edit distance (default: 0.52).",
    )
    parser.add_argument(
        "--heap-cap-mult",
        type=int,
        default=24,
        metavar="M",
        help="Per-word candidate cap is max(M*K, 48) before trimming (default: 24).",
    )
    args = parser.parse_args()

    if args.top_k < 1:
        raise SystemExit("--top-k must be >= 1")
    if not 0.0 < args.dice_min <= 1.0:
        raise SystemExit("--dice-min must be in (0, 1]")
    if args.heap_cap_mult < 4:
        raise SystemExit("--heap-cap-mult must be >= 4")

    words = load_word_entries(args.input)
    if not words:
        raise SystemExit(f"No words loaded from {args.input}")

    nonempty = write_similar_neighbors_json(
        words,
        args.output,
        top_k=args.top_k,
        dice_min=args.dice_min,
        heap_cap_mult=args.heap_cap_mult,
    )

    backend = "rapidfuzz" if _rf_bounded_distance is not None else "python"
    print(f"Distance backend: {backend}")

    print(
        f"Wrote {args.output} ({len(words)} entries, "
        f"{nonempty} with at least one neighbor)."
    )


if __name__ == "__main__":
    main()
