import React, { useState } from 'react';
import { 
  ShieldCheck, 
  GraduationCap, 
  Lock, 
  Mail, 
  ArrowRight, 
  Eye, 
  EyeOff, 
  BookOpen, 
  Sparkles,
  FileCheck2,
  FileSpreadsheet
} from 'lucide-react';
import { useApp } from '../context/AppContext';

export default function LoginPage() {
  const { login, loading } = useApp();
  const [email, setEmail] = useState('faculty@college.edu');
  const [password, setPassword] = useState('Faculty@123');
  const [showPassword, setShowPassword] = useState(false);
  const [selectedRole, setSelectedRole] = useState('faculty'); // 'faculty' | 'admin' | 'student'
  const [errorMsg, setErrorMsg] = useState('');

  const handleQuickFill = (role) => {
    setSelectedRole(role);
    setErrorMsg('');
    if (role === 'admin') {
      setEmail('admin@college.edu');
      setPassword('Admin@123');
    } else if (role === 'student') {
      setEmail('student1@college.edu');
      setPassword('Student@123');
    } else if (role === 'faculty') {
      setEmail('faculty@college.edu');
      setPassword('Faculty@123');
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrorMsg('');
    if (!email || !password) {
      setErrorMsg('Please enter both email and password.');
      return;
    }

    try {
      await login(email, password);
    } catch (err) {
      setErrorMsg(err.message || 'Authentication failed. Please verify credentials.');
    }
  };

  return (
    <div className="min-h-[82vh] flex items-center justify-center py-6 px-4 sm:px-6 lg:px-8">
      <div className="max-w-4xl w-full grid grid-cols-1 lg:grid-cols-12 gap-8 items-center">
        
        {/* Left Informational Showcase */}
        <div className="lg:col-span-6 space-y-6">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-50 border border-blue-200 text-blue-700 text-xs font-semibold">
            <Sparkles className="w-3.5 h-3.5" />
            Institutional Academic Portal
          </div>
          
          <h1 className="text-3xl sm:text-4xl font-extrabold text-slate-900 tracking-tight leading-tight">
            AI-Powered Syllabus & Examination System
          </h1>

          <p className="text-slate-600 text-sm sm:text-base leading-relaxed">
            A unified institutional platform for Department Faculty and Academic Administrators. Ingest syllabus curricula, analyze Course Outcomes (COs), extract textbooks from lawful repositories, and automatically synthesize exam papers mapped to Bloom's Taxonomy in custom Word (.docx) templates.
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2">
            <div className="p-3 bg-white rounded-xl border border-slate-200 shadow-xs flex items-start gap-3">
              <div className="p-2 rounded-lg bg-indigo-50 text-indigo-700 shrink-0">
                <ShieldCheck className="w-5 h-5" />
              </div>
              <div>
                <h4 className="text-xs font-bold text-slate-900">Admin Control</h4>
                <p className="text-[11px] text-slate-500">Manage faculty department-wise & designation-wise with full CRUD.</p>
              </div>
            </div>

            <div className="p-3 bg-white rounded-xl border border-slate-200 shadow-xs flex items-start gap-3">
              <div className="p-2 rounded-lg bg-blue-50 text-blue-700 shrink-0">
                <GraduationCap className="w-5 h-5" />
              </div>
              <div>
                <h4 className="text-xs font-bold text-slate-900">Faculty Workspace</h4>
                <p className="text-[11px] text-slate-500">Upload syllabus & PPT lecture notes with automatic book citation discovery.</p>
              </div>
            </div>

            <div className="p-3 bg-white rounded-xl border border-slate-200 shadow-xs flex items-start gap-3">
              <div className="p-2 rounded-lg bg-emerald-50 text-emerald-700 shrink-0">
                <FileCheck2 className="w-5 h-5" />
              </div>
              <div>
                <h4 className="text-xs font-bold text-slate-900">CO & Bloom's Gen</h4>
                <p className="text-[11px] text-slate-500">Synthesize exam questions mapped to CO1-CO6 with faculty validation.</p>
              </div>
            </div>

            <div className="p-3 bg-white rounded-xl border border-slate-200 shadow-xs flex items-start gap-3">
              <div className="p-2 rounded-lg bg-amber-50 text-amber-700 shrink-0">
                <FileSpreadsheet className="w-5 h-5" />
              </div>
              <div>
                <h4 className="text-xs font-bold text-slate-900">Word (.docx) Export</h4>
                <p className="text-[11px] text-slate-500">Inject questions into university formats or custom institution templates.</p>
              </div>
            </div>
          </div>
        </div>

        {/* Right Authentication Card */}
        <div className="lg:col-span-6 bg-white border border-slate-200 rounded-2xl shadow-xl p-6 sm:p-8">
          
          {/* Role selector tabs */}
          <div className="flex bg-slate-100 p-1 rounded-xl mb-6">
            <button
              type="button"
              onClick={() => handleQuickFill('faculty')}
              className={`flex-1 py-2 rounded-lg text-xs font-bold flex items-center justify-center gap-1.5 transition-all ${
                selectedRole === 'faculty'
                  ? 'bg-white text-blue-700 shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <GraduationCap className="w-4 h-4" />
              Faculty Login
            </button>
            <button
              type="button"
              onClick={() => handleQuickFill('student')}
              className={`flex-1 py-2 rounded-lg text-xs font-bold flex items-center justify-center gap-1.5 transition-all ${
                selectedRole === 'student'
                  ? 'bg-white text-teal-700 shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <BookOpen className="w-4 h-4" />
              Student Login
            </button>
            <button
              type="button"
              onClick={() => handleQuickFill('admin')}
              className={`flex-1 py-2 rounded-lg text-xs font-bold flex items-center justify-center gap-1.5 transition-all ${
                selectedRole === 'admin'
                  ? 'bg-white text-indigo-700 shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <ShieldCheck className="w-4 h-4" />
              Admin Login
            </button>
          </div>

          <div className="mb-6">
            <h2 className="text-xl font-bold text-slate-900">
              {selectedRole === 'admin' 
                ? 'Academic Administrator Portal' 
                : selectedRole === 'student' 
                  ? 'Student Adaptive Learning Portal' 
                  : 'Faculty Member Portal'}
            </h2>
            <p className="text-xs text-slate-500 mt-1">
              {selectedRole === 'admin'
                ? 'Sign in to manage faculty directory, departments, and institutional settings.'
                : selectedRole === 'student'
                  ? 'Sign in to take diagnostic tests, access course syllabuses, and track your cognitive mastery.'
                  : 'Sign in to upload course materials, extract books, and generate question papers.'}
            </p>
          </div>

          {errorMsg && (
            <div className="mb-4 p-3 rounded-lg bg-red-50 border border-red-200 text-xs text-red-700 font-medium">
              {errorMsg}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                Institutional Email
              </label>
              <div className="relative">
                <Mail className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@college.edu"
                  className="w-full pl-9 pr-3 py-2 text-xs sm:text-sm rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                Password
              </label>
              <div className="relative">
                <Lock className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type={showPassword ? 'text' : 'password'}
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full pl-9 pr-10 py-2 text-xs sm:text-sm rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full mt-2 py-2.5 px-4 bg-gradient-to-r from-blue-700 to-indigo-600 hover:from-blue-800 hover:to-indigo-700 text-white font-semibold text-xs sm:text-sm rounded-xl shadow-md transition-all flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
            >
              {loading ? (
                <span>Signing in...</span>
              ) : (
                <>
                  <span>Sign In as {selectedRole === 'admin' ? 'Administrator' : selectedRole === 'student' ? 'Student' : 'Faculty'}</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </form>

          {/* Quick Demo Credentials helper */}
          <div className="mt-6 pt-5 border-t border-slate-100">
            <div className="text-[11px] font-semibold text-slate-500 mb-2 flex items-center justify-between">
              <span>Quick Demo Fill:</span>
              <span className="text-[10px] text-blue-600 font-normal">Click to auto-fill</span>
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => handleQuickFill('student')}
                className="px-2.5 py-1 text-[11px] rounded-md bg-teal-50 hover:bg-teal-100 text-teal-700 border border-teal-200 transition-colors"
              >
                Student 1 (Aarav): <code className="font-mono font-bold">student1@college.edu</code>
              </button>
              <button
                type="button"
                onClick={() => {
                  setSelectedRole('student');
                  setEmail('student2@college.edu');
                  setPassword('Student@123');
                }}
                className="px-2.5 py-1 text-[11px] rounded-md bg-teal-50 hover:bg-teal-100 text-teal-700 border border-teal-200 transition-colors"
              >
                Student 2 (Diya): <code className="font-mono font-bold">student2@college.edu</code>
              </button>
              <button
                type="button"
                onClick={() => handleQuickFill('faculty')}
                className="px-2.5 py-1 text-[11px] rounded-md bg-blue-50 hover:bg-blue-100 text-blue-700 border border-blue-200 transition-colors"
              >
                CSE Faculty: <code className="font-mono font-bold">faculty@college.edu</code>
              </button>
              <button
                type="button"
                onClick={() => handleQuickFill('admin')}
                className="px-2.5 py-1 text-[11px] rounded-md bg-indigo-50 hover:bg-indigo-100 text-indigo-700 border border-indigo-200 transition-colors"
              >
                Dean (Admin): <code className="font-mono font-bold">admin@college.edu</code>
              </button>
            </div>
          </div>

        </div>

      </div>
    </div>
  );
}
