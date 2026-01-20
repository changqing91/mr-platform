import * as tus from 'tus-js-client';

export const TUSD_ENDPOINT = import.meta.env.VITE_TUSD_ENDPOINT;
export const TUSD_PATH_PREFIX = import.meta.env.VITE_TUSD_PATH_PREFIX;

export const uploadFile = (file, onProgress) => {
    return new Promise((resolve, reject) => {
        const upload = new tus.Upload(file, {
            endpoint: TUSD_ENDPOINT,
            retryDelays: [0, 3000, 5000, 10000, 20000],
            metadata: {
                filename: file.name,
                filetype: file.type
            },
            onError: (error) => {
                reject(error);
            },
            onProgress: (bytesUploaded, bytesTotal) => {
                if (onProgress) {
                    onProgress(bytesUploaded, bytesTotal);
                }
            },
            onSuccess: () => {
                resolve(upload);
            }
        });
        upload.start();
    });
};
