import React from 'react';
import { Check, AlertTriangle, Bell } from 'lucide-react';

const NotificationToast = ({ notifications }) => {
    return (
        <div className="fixed top-4 left-1/2 -translate-x-1/2 z-[100] flex flex-col gap-2 pointer-events-none">
            {notifications.map(n => (
                <div key={n.id} className={`pointer-events-auto px-4 py-3 rounded-lg shadow-xl flex items-center gap-3 animate-in slide-in-from-top-4 fade-in ${n.type === 'success' ? 'bg-white border-l-4 border-green-500 text-gray-800' : (n.type === 'error' ? 'bg-red-50 text-red-800 border-l-4 border-red-500' : 'bg-gray-800 text-white border-l-4 border-primary')}`}>
                    {n.type === 'success' && <Check size={18} className="text-green-500" />}
                    {n.type === 'error' && <AlertTriangle size={18} className="text-red-500" />}
                    {n.type === 'info' && <Bell size={18} className="text-primary" />}
                    <span className="font-medium">{n.message}</span>
                </div>
            ))}
        </div>
    );
};

export default NotificationToast;
