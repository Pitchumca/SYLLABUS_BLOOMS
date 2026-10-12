import React, { useEffect, useState } from 'react';
import { Bell, Check, CheckCheck, Clock, RefreshCw } from 'lucide-react';
import { api } from '../../services/api';
import { useApp } from '../../context/AppContext';

export default function StudentNotificationsPage() {
  const { notify } = useApp();
  const [notifications, setNotifications] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchNotifications();
  }, []);

  const fetchNotifications = async () => {
    try {
      setLoading(true);
      const data = await api.getStudentNotifications();
      setNotifications(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleMarkRead = async (id) => {
    try {
      await api.markNotificationRead(id);
      setNotifications(prev => prev.map(n => n.id === id ? { ...n, is_read: true } : n));
      notify('Marked notification as read', 'success');
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6 pb-12">
      <div className="bg-white rounded-2xl border border-slate-200 shadow-xs p-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-900 flex items-center gap-2">
            <Bell className="w-5 h-5 text-blue-600" />
            Faculty & Academic Notifications
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Official announcements, diagnostic test assignments, and personalized remedial notices.
          </p>
        </div>

        <button
          onClick={fetchNotifications}
          className="p-2 text-slate-500 hover:text-slate-800 rounded-lg hover:bg-slate-100 transition-colors"
          title="Refresh"
        >
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {loading ? (
        <div className="min-h-[40vh] flex flex-col items-center justify-center gap-2">
          <RefreshCw className="w-6 h-6 text-blue-600 animate-spin" />
          <span className="text-xs text-slate-500">Loading notifications...</span>
        </div>
      ) : notifications.length === 0 ? (
        <div className="p-8 text-center bg-white rounded-2xl border border-slate-200 text-slate-500 text-xs">
          No notifications found.
        </div>
      ) : (
        <div className="space-y-3">
          {notifications.map((n) => (
            <div 
              key={n.id}
              className={`p-4 rounded-xl border transition-all ${
                n.is_read 
                  ? 'bg-white border-slate-200' 
                  : 'bg-blue-50/40 border-blue-200 shadow-xs'
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-bold text-slate-900">{n.title}</h3>
                    {!n.is_read && (
                      <span className="text-[10px] font-bold px-1.5 py-0.2 rounded bg-blue-600 text-white">
                        New
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-slate-600 leading-relaxed">
                    {n.message}
                  </p>
                </div>

                {!n.is_read && (
                  <button
                    onClick={() => handleMarkRead(n.id)}
                    className="shrink-0 px-2.5 py-1 rounded-lg bg-white border border-slate-200 hover:bg-blue-50 text-[11px] font-semibold text-blue-700 flex items-center gap-1 transition-colors"
                  >
                    <Check className="w-3 h-3" />
                    <span>Mark Read</span>
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
