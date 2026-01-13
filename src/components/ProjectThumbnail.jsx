import React from 'react';
import { Box, Layers } from 'lucide-react';

const ProjectThumbnail = ({ project, className }) => {
    if (project?.thumbnail) {
        return <img src={project.thumbnail} alt={project.name} className={`${className} object-cover`} />;
    }

    const colors = [
        ['#3b82f6', '#1d4ed8'], ['#10b981', '#047857'], ['#8b5cf6', '#6d28d9'],
        ['#f59e0b', '#b45309'], ['#ef4444', '#b91c1c'], ['#6366f1', '#4338ca'],
        ['#ec4899', '#be185d'], ['#14b8a6', '#0f766e'],
    ];
    
    const index = (project?.id || 0) % colors.length;
    const [c1, c2] = colors[index];

    return (
        <div className={`${className} flex items-center justify-center relative overflow-hidden`} style={{ background: `linear-gradient(135deg, ${c1}, ${c2})` }}>
            <div className="absolute inset-0 opacity-20" style={{ backgroundImage: 'radial-gradient(circle at 2px 2px, white 1px, transparent 0)', backgroundSize: '16px 16px' }}></div>
            {project?.type === 'VRED' ? <Box className="text-white/40 w-1/3 h-1/3" /> : <Layers className="text-white/40 w-1/3 h-1/3" />}
        </div>
    );
};

export default ProjectThumbnail;
