import { Ruler, Flashlight, Scissors, Disc, Move, Mic, PenTool } from 'lucide-react';

export const THEME_COLOR = '#39C5BB';

export const INITIAL_PROJECTS = [
    { id: 1, name: 'Audi RS e-tron GT', type: 'VRED', thumbnail: null, size: '4.2 GB', date: '2023-10-15', tags: ['Concept', 'EV', 'Exterior'] },
    { id: 3, name: 'Mercedes-Benz Vision', type: 'VRED', thumbnail: null, size: '5.1 GB', date: '2023-11-02', tags: ['Concept', 'Sedan'] },
    { id: 5, name: 'Tesla Cybertruck', type: 'VRED', thumbnail: null, size: '1.5 GB', date: '2023-09-20', tags: ['Truck', 'EV', 'Low Poly'] },
    { id: 6, name: 'Cyberpunk Concept', type: 'VRED', thumbnail: null, size: '6.2 GB', date: '2023-12-05', tags: ['Sci-Fi', 'Concept'] },
    { id: 7, name: 'Ferrari F8 Tributo', type: 'VRED', thumbnail: null, size: '3.5 GB', date: '2023-08-10', tags: ['Sport', 'Coupe'] },
];

export const INITIAL_MACHINES = [
    { id: 'm1', name: 'Render Node 01', ip: '192.168.1.101', port: '8888', status: 'idle', currentProject: null, health: 'good' },
    { id: 'm2', name: 'Render Node 02', ip: '192.168.1.102', port: '8888', status: 'idle', currentProject: null, health: 'good' },
    { id: 'm3', name: 'VR Station A', ip: '192.168.1.105', port: '9001', status: 'running', currentProject: 1, health: 'good' }, 
    { id: 'm4', name: 'HoloLens Proxy', ip: '192.168.1.110', port: '8080', status: 'offline', currentProject: null, health: 'bad' },
    { id: 'm5', name: 'Render Node 03', ip: '192.168.1.103', port: '8888', status: 'idle', currentProject: null, health: 'good' }, 
    { id: 'm6', name: 'Render Node 04', ip: '192.168.1.104', port: '8888', status: 'idle', currentProject: null, health: 'good' }, 
];

export const MR_TOOLS = [
    { id: 'measure', name: '测量工具', icon: Ruler, description: '点对点距离测量' },
    { id: 'flashlight', name: '手电筒工具', icon: Flashlight, description: '虚拟手电筒照明' },
    { id: 'section', name: '剖面工具', icon: Scissors, description: 'X/Y/Z轴剖面裁剪' },
    { id: 'turntable', name: '展示台工具', icon: Disc, description: '自动旋转展示台' },
    { id: 'adjust', name: '物体调整工具', icon: Move, description: '移动/旋转/缩放' },
    { id: 'voice_note', name: '语音标注工具', icon: Mic, description: '添加语音注释' },
    { id: 'draw_note', name: '图形标注工具', icon: PenTool, description: '空间手绘标注' },
];
