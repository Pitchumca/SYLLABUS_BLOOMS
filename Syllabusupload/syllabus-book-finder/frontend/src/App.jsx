import React from 'react';
import { AppProvider, useApp } from './context/AppContext';
import Navbar from './components/Navbar';
import Footer from './components/Footer';
import Notification from './components/Notification';
import HomePage from './pages/HomePage';
import UploadPage from './pages/UploadPage';
import ReviewPage from './pages/ReviewPage';
import ResultsPage from './pages/ResultsPage';
import AnalyticsPage from './pages/AnalyticsPage';
import ExportPage from './pages/ExportPage';
import AboutPage from './pages/AboutPage';
import LoginPage from './pages/LoginPage';
import FacultyManagementPage from './pages/FacultyManagementPage';
import QuestionPaperPage from './pages/QuestionPaperPage';
import StudentDashboardPage from './pages/student/StudentDashboardPage';
import CourseLearningPage from './pages/student/CourseLearningPage';
import StudentCoursesPage from './pages/student/StudentCoursesPage';
import StudentAssessmentsPage from './pages/student/StudentAssessmentsPage';
import StudentLearningPlanPage from './pages/student/StudentLearningPlanPage';
import StudentProgressPage from './pages/student/StudentProgressPage';
import StudentResourcesPage from './pages/student/StudentResourcesPage';
import StudentNotificationsPage from './pages/student/StudentNotificationsPage';
import StudentProfilePage from './pages/student/StudentProfilePage';

function AppContent() {
  const { activeTab, user, isStudent, isAdmin, isFaculty } = useApp();

  // If user is not authenticated and is on login tab or unauthenticated
  if (!user && activeTab === 'login') {
    return (
      <div className="flex flex-col min-h-screen bg-slate-50/50">
        <Navbar />
        <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <LoginPage />
        </main>
        <Footer />
        <Notification />
      </div>
    );
  }

  return (
    <div className="flex flex-col min-h-screen bg-slate-50/50">
      <Navbar />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {activeTab === 'login' && <LoginPage />}
        
        {/* Admin & Faculty Views */}
        {activeTab === 'home' && (isStudent ? <StudentDashboardPage /> : <HomePage />)}
        {activeTab === 'faculty-mgmt' && (isAdmin ? <FacultyManagementPage /> : <LoginPage />)}
        {activeTab === 'question-paper' && (isStudent ? <StudentDashboardPage /> : <QuestionPaperPage />)}
        {activeTab === 'upload' && (isStudent ? <StudentDashboardPage /> : <UploadPage />)}
        {activeTab === 'review' && (isStudent ? <StudentDashboardPage /> : <ReviewPage />)}
        {activeTab === 'results' && (isStudent ? <StudentDashboardPage /> : <ResultsPage />)}
        {activeTab === 'analytics' && (isStudent ? <StudentDashboardPage /> : <AnalyticsPage />)}
        {activeTab === 'export' && (isStudent ? <StudentDashboardPage /> : <ExportPage />)}

        {/* Student Views */}
        {activeTab === 'student-dashboard' && <StudentDashboardPage />}
        {activeTab === 'student-courses' && <StudentCoursesPage />}
        {activeTab === 'student-course-detail' && <CourseLearningPage />}
        {activeTab === 'student-assessments' && <StudentAssessmentsPage />}
        {activeTab === 'student-plans' && <StudentLearningPlanPage />}
        {activeTab === 'student-progress' && <StudentProgressPage />}
        {activeTab === 'student-resources' && <StudentResourcesPage />}
        {activeTab === 'student-notifications' && <StudentNotificationsPage />}
        {activeTab === 'student-profile' && <StudentProfilePage />}

        {/* Common Views */}
        {activeTab === 'about' && <AboutPage />}
      </main>

      <Footer />
      <Notification />
    </div>
  );
}

export default function App() {
  return (
    <AppProvider>
      <AppContent />
    </AppProvider>
  );
}
