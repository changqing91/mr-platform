import React from 'react';
import { Loader2 } from 'lucide-react';
import { THEME_COLOR } from '../constants';

const UploadOverlay = ({ progress }) => {
    return (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[60] flex items-center justify-center animate-in fade-in">
            <div className="bg-white p-8 rounded-2xl shadow-2xl w-[400px] border border-gray-100 flex flex-col items-center">
                <div className="relative mb-6">
                    <div className="w-20 h-20 rounded-full border-4 border-gray-100"></div>
                    <div 
                        className="absolute inset-0 w-20 h-20 rounded-full border-4 border-t-transparent animate-spin"
                        style={{ borderColor: `${THEME_COLOR} transparent transparent transparent` }}
                    ></div>
                    <div className="absolute inset-0 flex items-center justify-center font-bold text-lg text-gray-700">
                        {progress}%
                    </div>
                </div>
                
                <h3 className="text-xl font-bold text-gray-800 mb-2">正在上传文件...</h3>
                <p className="text-gray-500 text-sm mb-6 text-center">请勿关闭页面或刷新</p>
                
                <div className="w-full bg-gray-100 rounded-full h-2 overflow-hidden">
                    <div 
                        className="h-full transition-all duration-300 ease-out rounded-full"
                        style={{ 
                            width: `${progress}%`,
                            backgroundColor: THEME_COLOR 
                        }}
                    ></div>
                </div>
            </div>
        </div>
    );
};

export default UploadOverlay;
