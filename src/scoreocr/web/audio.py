import base64

from scoreocr.verovio_util import new_toolkit


def musicxml_to_midi(xml_text: str) -> bytes:
    tk = new_toolkit()
    tk.setOptions({"breaks": "encoded"})
    if not tk.loadData(xml_text):
        raise RuntimeError("verovio failed to load MusicXML for MIDI export")
    return base64.b64decode(tk.renderToMIDI())
