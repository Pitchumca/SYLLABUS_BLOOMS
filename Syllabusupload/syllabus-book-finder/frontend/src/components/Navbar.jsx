import React, { useState } from 'react';
import { 
  BookOpen, 
  UploadCloud, 
  CheckSquare, 
  Search, 
  BarChart3, 
  Download, 
  HelpCircle, 
  Menu, 
  X,
  FileText,
  Users,
  Sparkles,
  LogOut,
  LogIn,
  ShieldCheck,
  GraduationCap,
  LayoutDashboard,
  TrendingUp,
  Library,
  Bell,
  UserCheck,
  Award,
  Compass
} from 'lucide-react';
import { useApp } from '../context/AppContext';

export default function Navbar() {
  const { activeTab, setActiveTab, currentSyllabus, books, user, logout, isAdmin, isFaculty, isStudent, studentNotifications } = useApp();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  // Dynamic Navigation Items according to authentication role
  let navItems = [];
  if (isAdmin) {
    navItems = [
      { id: 'faculty-mgmt', label: 'Faculty Directory', icon: Users },
      { id: 'question-paper', label: 'Question Papers', icon: Sparkles },
      { id: 'upload', label: 'Syllabus & Content', icon: UploadCloud },
      { id: 'review', label: 'Review Books', icon: CheckSquare, badge: books.length > 0 ? books.length : null },
      { id: 'analytics', label: 'Analytics', icon: BarChart3 },
      { id: 'export', label: 'Export Reports', icon: Download },
      { id: 'about', label: 'About & Policy', icon: HelpCircle },
    ];
  } else if (isFaculty) {
    navItems = [
      { id: 'home', label: 'Home', icon: BookOpen },
      { id: 'question-paper', label: 'Question Paper Gen', icon: Sparkles },
      { id: 'upload', label: 'Upload & Content', icon: UploadCloud },
      { id: 'review', label: 'Review Books', icon: CheckSquare, badge: books.length > 0 ? books.length : null },
      { id: 'results', label: 'Search Results', icon: Search },
      { id: 'analytics', label: 'Analytics', icon: BarChart3 },
      { id: 'export', label: 'Export Reports', icon: Download },
      { id: 'about', label: 'About & Policy', icon: HelpCircle },
    ];
  } else if (isStudent) {
    const unreadCount = studentNotifications?.filter(n => !n.is_read)?.length || null;
    navItems = [
      { id: 'student-dashboard', label: 'Dashboard', icon: LayoutDashboard },
      { id: 'student-courses', label: 'My Courses', icon: BookOpen },
      { id: 'student-assessments', label: 'Assessments', icon: Award },
      { id: 'student-plans', label: 'Learning Plan', icon: Sparkles },
      { id: 'student-progress', label: 'My Progress', icon: TrendingUp },
      { id: 'student-resources', label: 'Resources', icon: Library },
      { id: 'student-notifications', label: 'Notifications', icon: Bell, badge: unreadCount },
      { id: 'student-profile', label: 'Profile', icon: UserCheck },
    ];
  } else {
    navItems = [
      { id: 'login', label: 'Sign In', icon: LogIn },
      { id: 'about', label: 'About & Policy', icon: HelpCircle },
    ];
  }

  const handleNav = (id) => {
    setActiveTab(id);
    setMobileMenuOpen(false);
  };

  return (
    <header className="sticky top-0 z-40 bg-white/95 backdrop-blur border-b border-slate-200 shadow-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          
          {/* Logo & Title */}
          <div 
            className="flex items-center gap-3 cursor-pointer group"
            onClick={() => handleNav(user ? (isAdmin ? 'faculty-mgmt' : (isStudent ? 'student-dashboard' : 'home')) : 'login')}
          >
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-blue-700 to-indigo-600 flex items-center justify-center text-white shadow-md group-hover:scale-105 transition-transform">
              <BookOpen className="w-5 h-5" />
            </div>
            <div>
              <span className="font-bold text-slate-900 tracking-tight text-base sm:text-lg block leading-tight">
                Syllabus Book Finder
              </span>
              <span className="text-[10px] text-blue-600 font-bold tracking-wider uppercase whitespace-nowrap">
                AI Curriculum & QP Suite
              </span>
            </div>
          </div>

          {/* Desktop Navigation */}
          <nav className="hidden xl:flex items-center gap-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => handleNav(item.id)}
                  className={`relative flex items-center gap-1.5 px-2.5 py-2 rounded-lg text-xs font-semibold tracking-wide transition-all ${
                    isActive
                      ? 'bg-blue-50 text-blue-700 shadow-xs'
                      : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100/70'
                  }`}
                >
                  <Icon className={`w-3.5 h-3.5 ${isActive ? 'text-blue-700' : 'text-slate-500'}`} />
                  <span>{item.label}</span>
                  {item.badge && (
                    <span className="ml-1 px-1.5 py-0.5 rounded-full text-[10px] font-bold bg-blue-100 text-blue-800">
                      {item.badge}
                    </span>
                  )}
                  {isActive && (
                    <span className="absolute bottom-0 left-2.5 right-2.5 h-0.5 bg-blue-600 rounded-full" />
                  )}
                </button>
              );
            })}
          </nav>

          {/* User Account / Auth Actions */}
          <div className="hidden lg:flex items-center gap-3">
            {user ? (
              <div className="flex items-center gap-2.5 pl-2 border-l border-slate-200">
                <div className="flex items-center gap-2">
                  <div className={`w-8 h-8 rounded-full text-white font-bold text-xs flex items-center justify-center shadow-xs ${
                    isAdmin 
                      ? 'bg-gradient-to-tr from-indigo-600 to-purple-600' 
                      : isStudent 
                        ? 'bg-gradient-to-tr from-teal-600 to-emerald-600' 
                        : 'bg-gradient-to-tr from-blue-600 to-indigo-600'
                  }`}>
                    {user.full_name?.charAt(0).toUpperCase() || 'U'}
                  </div>
                  <div className="text-left">
                    <span className="text-xs font-bold text-slate-800 block leading-tight truncate max-w-[140px]">
                      {user.full_name}
                    </span>
                    <span className={`inline-flex items-center gap-1 text-[10px] font-semibold px-1.5 py-0.2 rounded ${
                      isAdmin 
                        ? 'bg-indigo-50 text-indigo-700' 
                        : isStudent 
                          ? 'bg-teal-50 text-teal-700 border border-teal-200/50' 
                          : 'bg-blue-50 text-blue-700'
                    }`}>
                      {isAdmin ? <ShieldCheck className="w-2.5 h-2.5" /> : <GraduationCap className="w-2.5 h-2.5" />}
                      {isAdmin ? 'Admin' : isStudent ? 'Student • IV Sem' : `${user.department?.split(' ')[0] || 'Faculty'}`}
                    </span>
                  </div>
                </div>

                <button
                  onClick={logout}
                  className="p-1.5 rounded-lg text-slate-400 hover:text-red-600 hover:bg-red-50 transition-colors"
                  title="Sign Out"
                >
                  <LogOut className="w-4 h-4" />
                </button>
              </div>
            ) : (
              <button
                onClick={() => handleNav('login')}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 rounded-lg shadow-xs transition-colors"
              >
                <LogIn className="w-3.5 h-3.5" />
                <span>Sign In</span>
              </button>
            )}
          </div>

          {/* Mobile menu button */}
          <div className="xl:hidden flex items-center gap-2">
            {user && (
              <button
                onClick={logout}
                className="p-1.5 rounded-lg text-slate-500 hover:text-red-600"
                title="Sign Out"
              >
                <LogOut className="w-4 h-4" />
              </button>
            )}
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="p-2 rounded-lg text-slate-600 hover:text-slate-900 hover:bg-slate-100"
              aria-label="Toggle navigation"
            >
              {mobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
            </button>
          </div>

        </div>
      </div>

      {/* Mobile Menu Dropdown */}
      {mobileMenuOpen && (
        <div className="xl:hidden border-b border-slate-200 bg-white px-4 pt-2 pb-4 space-y-1 shadow-md">
          {user && (
            <div className="px-3 py-2 mb-2 bg-slate-50 rounded-lg text-xs font-medium text-slate-700 flex items-center justify-between">
              <div>
                <span className="font-bold text-slate-900 block">{user.full_name}</span>
                <span className="text-[11px] text-slate-500">{user.role.toUpperCase()} • {user.department}</span>
              </div>
              <button
                onClick={logout}
                className="text-xs font-semibold text-red-600 hover:underline"
              >
                Sign Out
              </button>
            </div>
          )}

          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => handleNav(item.id)}
                className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-blue-50 text-blue-700'
                    : 'text-slate-700 hover:bg-slate-100'
                }`}
              >
                <div className="flex items-center gap-2.5">
                  <Icon className={`w-4 h-4 ${isActive ? 'text-blue-700' : 'text-slate-500'}`} />
                  <span>{item.label}</span>
                </div>
                {item.badge && (
                  <span className="px-2 py-0.5 rounded-full text-xs font-bold bg-blue-100 text-blue-800">
                    {item.badge}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      )}
    </header>
  );
}
