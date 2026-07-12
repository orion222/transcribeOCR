from lxml import etree
from pydantic import BaseModel

from scoreocr.models import ScoreMeta, measure_total


class Issue(BaseModel):
    measure: int | None = None
    code: str
    message: str


def validate_musicxml(
    xml: bytes, meta: ScoreMeta, expected_measure_numbers: list[int]
) -> list[Issue]:
    issues: list[Issue] = []
    try:
        root = etree.fromstring(xml)
    except etree.XMLSyntaxError as exc:
        return [Issue(code="xml", message=str(exc))]

    measures = root.findall(".//measure")
    found_numbers = [int(m.get("number")) for m in measures]
    if len(found_numbers) != len(expected_measure_numbers):
        issues.append(Issue(
            code="measure-count",
            message=f"expected {len(expected_measure_numbers)} measures, found {len(found_numbers)}",
        ))
    if found_numbers != expected_measure_numbers:
        issues.append(Issue(
            code="numbering",
            message=f"measure numbers {found_numbers} != expected {expected_measure_numbers}",
        ))

    expected = measure_total(meta)
    for m in measures:
        number = int(m.get("number"))
        sums: dict[str, int] = {}
        for note in m.findall("note"):
            if note.find("grace") is not None:
                if note.find("duration") is not None:
                    issues.append(Issue(
                        measure=number, code="grace-duration",
                        message="grace note must not carry a duration",
                    ))
                continue
            if note.find("chord") is not None:
                continue  # chord members share the first note's time
            voice = note.findtext("voice") or "1"
            sums[voice] = sums.get(voice, 0) + int(note.findtext("duration"))
        for voice, total in sums.items():
            if total != expected:
                issues.append(Issue(
                    measure=number, code="duration",
                    message=f"voice {voice}: expected {expected} divisions, parsed {total}",
                ))

    if measures:
        last = measures[-1]
        if last.findtext("barline/bar-style") != "light-heavy":
            issues.append(Issue(code="final-barline", message="missing final light-heavy barline"))
    return issues
