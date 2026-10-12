import React, { useEffect, useState } from 'react';
import { 
  UserCheck, 
  Mail, 
  Building, 
  Award, 
  GraduationCap, 
  Calendar, 
  ShieldCheck, 
  RefreshCw 
} from 'lucide-react';
import { useApp } from '../../context/AppContext';
import { api } from '../../services/api';

export default function StudentProfilePage() {
  const { user } = useApp();
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getStudentProfile()
      .then(data => setProfile(data))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="min-h-[50vh] flex flex-col items-center justify-center gap-2">
        <RefreshCw className="w-6 h-6 text-blue-600 animate-spin" />
        <span className="text-xs text-slate-500">Loading student profile...</span>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6 pb-12">
      <div className="bg-white rounded-2xl border border-slate-200 shadow-xs p-6 sm:p-8 space-y-6">
        <div className="flex items-center gap-4">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-tr from-teal-600 to-emerald-600 text-white font-black text-2xl flex items-center justify-center shadow-md">
            {user?.full_name?.charAt(0).toUpperCase() || 'S'}
          </div>
          <div>
            <h1 className="text-xl sm:text-2xl font-black text-slate-900">
              {profile?.full_name || user?.full_name}
            </h1>
            <p className="text-xs text-slate-500 mt-0.5">
              Role: <strong className="text-teal-700 font-semibold uppercase">Student</strong> • Standing: <span className="font-bold text-emerald-600">{profile?.academic_standing || 'Good'}</span>
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-4 border-t border-slate-100">
          <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200/70 space-y-1">
            <span className="text-[11px] font-semibold text-slate-500 block">Registration Number</span>
            <span className="text-sm font-bold text-slate-900">{profile?.register_number}</span>
          </div>

          <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200/70 space-y-1">
            <span className="text-[11px] font-semibold text-slate-500 block">Institutional Email</span>
            <span className="text-sm font-bold text-slate-900">{profile?.email}</span>
          </div>

          <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200/70 space-y-1">
            <span className="text-[11px] font-semibold text-slate-500 block">Academic Programme</span>
            <span className="text-sm font-bold text-slate-900">{profile?.programme}</span>
          </div>

          <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200/70 space-y-1">
            <span className="text-[11px] font-semibold text-slate-500 block">Department</span>
            <span className="text-sm font-bold text-slate-900">{profile?.department}</span>
          </div>

          <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200/70 space-y-1">
            <span className="text-[11px] font-semibold text-slate-500 block">Current Semester & Section</span>
            <span className="text-sm font-bold text-slate-900">{profile?.semester} ({profile?.section})</span>
          </div>

          <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200/70 space-y-1">
            <span className="text-[11px] font-semibold text-slate-500 block">Graduation Batch</span>
            <span className="text-sm font-bold text-slate-900">{profile?.batch_year}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
