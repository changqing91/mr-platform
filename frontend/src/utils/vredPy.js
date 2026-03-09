
import measure from './vredPy/measure.py?raw';
import flashlight from './vredPy/flashlight.py?raw';
import section from './vredPy/section.py?raw';
import turntable from './vredPy/turntable.py?raw';
import adjust from './vredPy/adjust.py?raw';
import voiceNote from './vredPy/voice_note.py?raw';
import drawNote from './vredPy/draw_note.py?raw';
import allTools from './vredPy/all_tools.py?raw';

// 旧版：单个工具脚本 (保留向后兼容)
export const TOOL_IMPLEMENTATIONS = {
    measure,
    flashlight,
    section,
    turntable,
    adjust,
    voice_note: voiceNote,
    draw_note: drawNote
};

// 新版：统一脚本 - 一次注入所有工具
export const ALL_TOOLS_SCRIPT = allTools;

// 生成切换工具的 Python 命令
export function getSwitchToolCommand(toolId) {
    return `switch_tool("${toolId}")`;
}

// 生成禁用所有工具的 Python 命令
export function getDisableAllCommand() {
    return 'disable_all_tools()';
}

// 生成完全清除的 Python 命令 (禁用工具 + 删除所有创建的节点 + 重置状态)
export function getCleanupAllCommand() {
    return 'cleanup_all_tools()';
}
