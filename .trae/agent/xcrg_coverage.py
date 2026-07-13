import os
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, TypedDict
from urllib.parse import unquote


class CoverageItem(TypedDict):
    source_file: str
    instance: str
    metric: str
    score: float
    details: dict[str, Any]
    source_report: str


class CoverageDiagnostic(TypedDict):
    status: str
    message: str
    source_report: str


class CoverageExtraction(TypedDict):
    items: list[CoverageItem]
    diagnostics: list[CoverageDiagnostic]


class _Cell(TypedDict):
    text: str
    hrefs: list[str]


class _Table(TypedDict):
    attributes: dict[str, str]
    rows: list[list[_Cell]]


class _Anchor(TypedDict):
    href: str
    text: str


class _XcrgHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[_Table] = []
        self.anchors: list[_Anchor] = []
        self._table: _Table | None = None
        self._row: list[_Cell] | None = None
        self._cell_parts: list[str] | None = None
        self._cell_preferred_parts: list[str] | None = None
        self._cell_hrefs: list[str] = []
        self._preferred_depth = 0
        self._anchor_href: str | None = None
        self._anchor_parts: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        attributes = {
            key.lower(): str(value or "")
            for key, value in attrs
        }
        if tag == "table" and self._table is None:
            self._table = {
                "attributes": attributes,
                "rows": [],
            }
        elif tag == "tr" and self._table is not None:
            self._row = []
        elif tag in {"td", "th"} and self._row is not None:
            self._cell_parts = []
            self._cell_preferred_parts = []
            self._cell_hrefs = []
        elif tag == "span" and self._cell_parts is not None:
            class_name = attributes.get("class", "")
            if any(
                part.startswith("tooltiptext")
                for part in class_name.split()
            ):
                self._preferred_depth += 1

        if tag == "a":
            href = attributes.get("href", "")
            if self._cell_parts is not None and href:
                self._cell_hrefs.append(href)
            self._anchor_href = href
            self._anchor_parts = []

    def handle_data(self, data: str) -> None:
        if self._cell_parts is not None:
            self._cell_parts.append(data)
            if self._preferred_depth and self._cell_preferred_parts is not None:
                self._cell_preferred_parts.append(data)
        if self._anchor_href is not None:
            self._anchor_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._anchor_href is not None:
            self.anchors.append(
                {
                    "href": self._anchor_href,
                    "text": _clean_text("".join(self._anchor_parts)),
                }
            )
            self._anchor_href = None
            self._anchor_parts = []
        elif tag == "span" and self._preferred_depth:
            self._preferred_depth -= 1
        elif tag in {"td", "th"} and self._row is not None:
            preferred = _clean_text(
                "".join(self._cell_preferred_parts or [])
            )
            text = preferred or _clean_text("".join(self._cell_parts or []))
            self._row.append(
                {
                    "text": text,
                    "hrefs": list(self._cell_hrefs),
                }
            )
            self._cell_parts = None
            self._cell_preferred_parts = None
            self._cell_hrefs = []
            self._preferred_depth = 0
        elif tag == "tr" and self._table is not None and self._row is not None:
            if self._row:
                self._table["rows"].append(self._row)
            self._row = None
        elif tag == "table" and self._table is not None:
            self.tables.append(self._table)
            self._table = None


def _clean_text(value: object) -> str:
    return " ".join(str(value or "").split())


def _instance_name(value: object) -> str:
    instance = re.sub(r"\s+\.", ".", _clean_text(value))
    if instance.startswith("his."):
        return "t" + instance
    return instance


def _header(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _clean_text(value).lower()).strip()


def _number(value: object) -> float:
    match = re.search(r"-?[0-9]+(?:\.[0-9]+)?", _clean_text(value))
    if not match:
        raise ValueError("not a numeric xcrg value: {!r}".format(value))
    return float(match.group(0))


def _detail_number(value: object) -> int | float:
    number = _number(value)
    return int(number) if number.is_integer() else round(number, 4)


def _score(value: object) -> float:
    return round(_number(value), 1)


def _relative_href(report_base: Path, path: Path) -> str:
    return Path(os.path.relpath(path, report_base)).as_posix()


def _read_xcrg_page(path: Path) -> _XcrgHtmlParser:
    parser = _XcrgHtmlParser()
    parser.feed(path.read_text(encoding="utf-8"))
    parser.close()
    return parser


def _row_map(table: _Table) -> list[dict[str, _Cell]]:
    rows = table["rows"]
    if len(rows) < 2:
        return []
    headers = [_header(cell["text"]) for cell in rows[0]]
    return [
        {
            header: cell
            for header, cell in zip(headers, row, strict=False)
            if header
        }
        for row in rows[1:]
    ]


def _find_table(
    tables: list[_Table],
    required_headers: set[str],
) -> _Table | None:
    for table in tables:
        if not table["rows"]:
            continue
        headers = {
            _header(cell["text"])
            for cell in table["rows"][0]
        }
        if required_headers <= headers:
            return table
    return None


def _project_source_file(raw_path: object, project_dir: Path) -> str | None:
    source = unquote(_clean_text(raw_path))
    if source.lower().startswith("file:"):
        source = source[5:]
    source = source.replace("\\", "/").strip()
    project = project_dir.resolve().as_posix().rstrip("/")
    source_folded = source.casefold()
    project_folded = project.casefold()
    if source_folded.startswith(project_folded + "/"):
        return source[len(project) + 1 :]

    marker = "/outputs/{}/".format(project_dir.name).casefold()
    marker_index = source_folded.find(marker)
    if marker_index >= 0:
        return source[marker_index + len(marker) :]

    is_absolute = source.startswith("/") or bool(
        re.match(r"^[A-Za-z]:/", source)
    )
    if not is_absolute:
        relative = source.removeprefix("./")
        if relative and not relative.startswith("../"):
            return relative
    return None


def _report_path(
    listing_path: Path,
    cell: _Cell,
) -> Path:
    href = next(iter(cell["hrefs"]), "")
    if not href:
        return listing_path
    return listing_path.parent / href


def _diagnostic(
    status: str,
    message: str,
    path: Path,
    report_base: Path,
) -> CoverageDiagnostic:
    return {
        "status": status,
        "message": _clean_text(message),
        "source_report": _relative_href(report_base, path),
    }


def _coverage_item(
    source_file: str,
    instance: str,
    metric: str,
    score: float,
    details: dict[str, Any],
    source_report: Path,
    report_base: Path,
) -> CoverageItem:
    return {
        "source_file": source_file,
        "instance": _instance_name(instance),
        "metric": metric,
        "score": round(score, 1),
        "details": details,
        "source_report": _relative_href(report_base, source_report),
    }


def _extract_file_items(
    path: Path,
    project_dir: Path,
    report_base: Path,
    target_threshold: float,
) -> list[CoverageItem]:
    parser = _read_xcrg_page(path)
    table = _find_table(
        parser.tables,
        {
            "file path",
            "statement coverage score",
            "branch coverage score",
            "condition coverage score",
            "toggle coverage score",
        },
    )
    if table is None:
        raise ValueError("unsupported files.html layout")

    metric_headers = {
        "statement": "statement coverage score",
        "branch": "branch coverage score",
        "condition": "condition coverage score",
        "toggle": "toggle coverage score",
    }
    items: list[CoverageItem] = []
    for row in _row_map(table):
        source_cell = row.get("file path")
        if source_cell is None:
            continue
        source_file = _project_source_file(
            source_cell["text"],
            project_dir,
        )
        if source_file is None:
            continue
        source_report = _report_path(path, source_cell)
        for metric, header_name in metric_headers.items():
            metric_cell = row.get(header_name)
            if metric_cell is None:
                continue
            value = _score(metric_cell["text"])
            if value < target_threshold:
                items.append(
                    _coverage_item(
                        source_file,
                        "",
                        metric,
                        value,
                        {
                            "scope": "file",
                            "name": source_file,
                        },
                        source_report,
                        report_base,
                    )
                )
    return items


def _extract_module_items(
    path: Path,
    project_dir: Path,
    report_base: Path,
    target_threshold: float,
) -> list[CoverageItem]:
    parser = _read_xcrg_page(path)
    table = _find_table(
        parser.tables,
        {
            "module name",
            "hierarchical instance s",
            "statement score",
            "branch score",
            "condition score",
            "toggle score",
            "module definition in file",
        },
    )
    if table is None:
        raise ValueError("unsupported modules.html layout")

    metric_headers = {
        "statement": "statement score",
        "branch": "branch score",
        "condition": "condition score",
        "toggle": "toggle score",
    }
    items: list[CoverageItem] = []
    for row in _row_map(table):
        source_cell = row.get("module definition in file")
        module_cell = row.get("module name")
        instance_cell = row.get("hierarchical instance s")
        if source_cell is None or module_cell is None:
            continue
        source_file = _project_source_file(
            source_cell["text"],
            project_dir,
        )
        if source_file is None:
            continue
        source_report = _report_path(path, module_cell)
        instance = instance_cell["text"] if instance_cell else ""
        for metric, header_name in metric_headers.items():
            metric_cell = row.get(header_name)
            if metric_cell is None:
                continue
            value = _score(metric_cell["text"])
            if value < target_threshold:
                items.append(
                    _coverage_item(
                        source_file,
                        instance,
                        metric,
                        value,
                        {
                            "scope": "module",
                            "name": module_cell["text"],
                        },
                        source_report,
                        report_base,
                    )
                )
    return items


def _group_source_file(
    parser: _XcrgHtmlParser,
    project_dir: Path,
) -> str:
    for anchor in parser.anchors:
        href = anchor["href"]
        candidate = anchor["text"] or href
        suffix = Path(
            candidate.removeprefix("file:").replace("\\", "/")
        ).suffix.lower()
        if not href.lower().startswith("file:") and suffix not in {
            ".v",
            ".sv",
            ".svh",
            ".vhd",
            ".vhdl",
        }:
            continue
        source_file = _project_source_file(
            candidate,
            project_dir,
        )
        if source_file is not None:
            return source_file
    return ""


def _group_instance(parser: _XcrgHtmlParser) -> str:
    table = next(
        (
            item
            for item in parser.tables
            if item["attributes"].get("id") == "sortable0"
        ),
        None,
    )
    if table is None:
        return ""
    rows = _row_map(table)
    if not rows:
        return ""
    name_cell = rows[0].get("name")
    return name_cell["text"] if name_cell else ""


def _functional_detail_items(
    path: Path,
    project_dir: Path,
    report_base: Path,
    target_threshold: float,
) -> tuple[str, str, list[CoverageItem]]:
    parser = _read_xcrg_page(path)
    source_file = _group_source_file(parser, project_dir)
    instance = _group_instance(parser)
    items: list[CoverageItem] = []
    for table_id, metric, scope in (
        ("sortable1", "cover_point", "cover_point"),
        ("sortable2", "cross", "cross"),
    ):
        table = next(
            (
                item
                for item in parser.tables
                if item["attributes"].get("id") == table_id
            ),
            None,
        )
        if table is None:
            continue
        for row in _row_map(table):
            name_cell = row.get("name")
            score_cell = row.get("percent")
            if name_cell is None or score_cell is None:
                continue
            value = _score(score_cell["text"])
            if value >= target_threshold:
                continue
            details: dict[str, Any] = {
                "scope": scope,
                "name": name_cell["text"],
            }
            for field in ("expected", "uncovered", "covered", "goal"):
                cell = row.get(field)
                if cell is not None and cell["text"]:
                    details[field] = _detail_number(cell["text"])
            items.append(
                _coverage_item(
                    source_file,
                    instance,
                    metric,
                    value,
                    details,
                    path,
                    report_base,
                )
            )
    return source_file, instance, items


def _extract_functional_items(
    path: Path,
    project_dir: Path,
    report_base: Path,
    target_threshold: float,
) -> tuple[list[CoverageItem], list[CoverageDiagnostic]]:
    parser = _read_xcrg_page(path)
    table = _find_table(
        parser.tables,
        {"score", "goal"},
    )
    if table is None:
        raise ValueError("unsupported groups.html layout")

    items: list[CoverageItem] = []
    diagnostics: list[CoverageDiagnostic] = []
    for row in _row_map(table):
        group_cell = next(
            (
                cell
                for cell in row.values()
                if any(
                    re.fullmatch(
                        r"grp[0-9]+\.html",
                        Path(href).name,
                        flags=re.IGNORECASE,
                    )
                    for href in cell["hrefs"]
                )
            ),
            None,
        )
        if group_cell is None:
            group_cell = row.get("group name") or row.get("name")
        score_cell = row.get("score")
        if group_cell is None or score_cell is None:
            continue
        group_score = _score(score_cell["text"])
        detail_path = _report_path(path, group_cell)
        source_file = ""
        instance = ""
        detail_items: list[CoverageItem] = []
        if detail_path.is_file():
            try:
                source_file, instance, detail_items = (
                    _functional_detail_items(
                        detail_path,
                        project_dir,
                        report_base,
                        target_threshold,
                    )
                )
            except (OSError, UnicodeDecodeError, ValueError) as exc:
                diagnostics.append(
                    _diagnostic(
                        "INVALID",
                        "无法解析 functional coverage 明细: {}".format(exc),
                        detail_path,
                        report_base,
                    )
                )
        else:
            diagnostics.append(
                _diagnostic(
                    "MISSING",
                    "缺少 functional coverage 明细页",
                    detail_path,
                    report_base,
                )
            )
        if group_score < target_threshold:
            items.append(
                _coverage_item(
                    source_file,
                    instance,
                    "functional_group",
                    group_score,
                    {
                        "scope": "functional_group",
                        "name": group_cell["text"],
                    },
                    detail_path,
                    report_base,
                )
            )
        items.extend(detail_items)
    return items, diagnostics


def extract_low_coverage_items(
    project_dir: str | Path,
    report_base: str | Path,
    target_threshold: float = 80.0,
) -> CoverageExtraction:
    threshold = float(target_threshold)
    if not 0.0 <= threshold <= 100.0:
        raise ValueError("coverage target must be between 0 and 100")

    project_path = Path(project_dir)
    report_base_path = Path(report_base)
    xcrg_dir = project_path / "reports" / "uvm_coverage_xcrg"
    pages = (
        (
            xcrg_dir / "codeCoverageReport" / "files.html",
            _extract_file_items,
        ),
        (
            xcrg_dir / "codeCoverageReport" / "modules.html",
            _extract_module_items,
        ),
    )
    items: list[CoverageItem] = []
    diagnostics: list[CoverageDiagnostic] = []
    for page_path, extractor in pages:
        if not page_path.is_file():
            diagnostics.append(
                _diagnostic(
                    "MISSING",
                    "缺少 xcrg 汇总页",
                    page_path,
                    report_base_path,
                )
            )
            continue
        try:
            items.extend(
                extractor(
                    page_path,
                    project_path,
                    report_base_path,
                    threshold,
                )
            )
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            diagnostics.append(
                _diagnostic(
                    "INVALID",
                    "无法解析 xcrg 汇总页: {}".format(exc),
                    page_path,
                    report_base_path,
                )
            )

    groups_path = (
        xcrg_dir
        / "functionalCoverageReport"
        / "groups.html"
    )
    if not groups_path.is_file():
        diagnostics.append(
            _diagnostic(
                "MISSING",
                "缺少 functional coverage 汇总页",
                groups_path,
                report_base_path,
            )
        )
    else:
        try:
            functional_items, functional_diagnostics = (
                _extract_functional_items(
                    groups_path,
                    project_path,
                    report_base_path,
                    threshold,
                )
            )
            items.extend(functional_items)
            diagnostics.extend(functional_diagnostics)
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            diagnostics.append(
                _diagnostic(
                    "INVALID",
                    "无法解析 functional coverage 汇总页: {}".format(exc),
                    groups_path,
                    report_base_path,
                )
            )

    items.sort(
        key=lambda item: (
            item["score"],
            item["metric"],
            item["source_file"],
            item["instance"],
            _clean_text(item["details"].get("name", "")),
        )
    )
    diagnostics.sort(
        key=lambda item: (
            item["status"],
            item["source_report"],
        )
    )
    return {
        "items": items,
        "diagnostics": diagnostics,
    }
