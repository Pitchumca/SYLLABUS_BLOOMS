import React from 'react';
import { CheckCircle2, AlertCircle, Info, X } from 'lucide-react';
import { useApp } from '../context/AppContext';

export default function Notification() {
  const { notification, closeNotification } = useApp();

  if (!notification) return null;

  const isSuccess = notification.type === 'success';
  const isError = notification.type === 'error';

  return (
    <div className="fixed bottom-5 right-5 z-50 max-w-md animate-fade-in transition-all">
      <div
        className={`flex items-start gap-3 p-4 rounded-xl shadow-lg border backdrop-blur-md ${
          isSuccess
            ? 'bg-emerald-50/95 border-emerald-300 text-emerald-900'
            : isError
            ? 'bg-rose-50/95 border-rose-300 text-rose-900'
            : 'bg-blue-50/95 border-blue-300 text-blue-900'
        }`}
      >
        <div className="shrink-0 mt-0.5">
          {isSuccess && <CheckCircle2 className="w-5 h-5 text-emerald-600" />}
          {isError && <AlertCircle className="w-5 h-5 text-rose-600" />}
          {!isSuccess && !isError && <Info className="w-5 h-5 text-blue-600" />}
        </div>
        <div className="flex-1 text-sm font-medium leading-snug">
          {notification.message}
        </div>
        <button
          onClick={closeNotification}
          className="text-slate-400 hover:text-slate-600 p-0.5 rounded-lg transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}
