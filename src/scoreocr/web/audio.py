import base64

import verovio


def musicxml_to_midi(xml_text: str) -> bytes:
    tk = verovio.toolkit()
    tk.setOptions({"breaks": "encoded"})
    if not tk.loadData(xml_text):
        raise RuntimeError("verovio failed to load MusicXML for MIDI export")
    return base64.b64decode(tk.renderToMIDI())
