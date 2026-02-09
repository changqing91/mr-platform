
import measure from './vredPy/measure.py?raw';
import flashlight from './vredPy/flashlight.py?raw';
import section from './vredPy/section.py?raw';
import turntable from './vredPy/turntable.py?raw';
import adjust from './vredPy/adjust.py?raw';
import voiceNote from './vredPy/voice_note.py?raw';
import drawNote from './vredPy/draw_note.py?raw';

export const TOOL_IMPLEMENTATIONS = {
    measure,
    flashlight,
    section,
    turntable,
    adjust,
    voice_note: voiceNote,
    draw_note: drawNote
};
