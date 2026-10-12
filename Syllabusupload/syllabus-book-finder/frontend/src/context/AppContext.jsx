import React, { createContext, useContext, useState, useEffect } from 'react';
import { api } from '../services/api';

const AppContext = createContext();

export function AppProvider({ children }) {
  // Auth state
  const [token, setToken] = useState(() => localStorage.getItem('auth_token') || null);
  const [user, setUser] = useState(() => {
    try {
      const stored = localStorage.getItem('auth_user');
      return stored ? JSON.parse(stored) : null;
    } catch {
      return null;
    }
  });

  const [currentPath, setCurrentPath] = useState(() => window.location.pathname + window.location.search);

  const [activeTab, setActiveTab] = useState(() => {
    const savedToken = localStorage.getItem('auth_token');
    const savedUser = localStorage.getItem('auth_user');
    if (!savedToken) return 'login';
    const path = window.location.pathname;
    if (path.startsWith('/question-papers') || ['/content', '/blueprint', '/export'].includes(path)) {
      return 'question-paper';
    }
    try {
      const u = JSON.parse(savedUser);
      if (u?.role === 'admin') return 'faculty-mgmt';
      if (u?.role === 'student') return 'student-dashboard';
      return 'home';
    } catch {
      return 'login';
    }
  });

  const navigate = (path) => {
    if (path !== window.location.pathname + window.location.search) {
      window.history.pushState({}, '', path);
      setCurrentPath(path);
      const cleanPath = path.split('?')[0];
      if (cleanPath.startsWith('/question-papers') || ['/content', '/blueprint', '/export'].includes(cleanPath)) {
        setActiveTab('question-paper');
      }
      window.dispatchEvent(new PopStateEvent('popstate'));
    }
  };

  useEffect(() => {
    const handlePopState = () => {
      const full = window.location.pathname + window.location.search;
      setCurrentPath(full);
      const cleanPath = window.location.pathname;
      if (cleanPath.startsWith('/question-papers') || ['/content', '/blueprint', '/export'].includes(cleanPath)) {
        setActiveTab('question-paper');
      }
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  const [currentSyllabus, setCurrentSyllabus] = useState(null);
  const [books, setBooks] = useState([]);
  const [searchResults, setSearchResults] = useState([]);
  const [analytics, setAnalytics] = useState(null);
  const [currentQuestionPaper, setCurrentQuestionPaper] = useState(null);
  const [courseOutcomes, setCourseOutcomes] = useState([]);
  const [contentFiles, setContentFiles] = useState([]);

  const [loading, setLoading] = useState(false);
  const [loadingMessage, setLoadingMessage] = useState('');
  const [notification, setNotification] = useState(null);

  // Student State
  const [selectedStudentCourseId, setSelectedStudentCourseId] = useState(null);
  const [studentDashboardData, setStudentDashboardData] = useState(null);
  const [studentCourses, setStudentCourses] = useState([]);
  const [studentNotifications, setStudentNotifications] = useState([]);

  // Validate session on mount
  useEffect(() => {
    if (token) {
      api.getMe()
        .then((userData) => {
          setUser(userData);
          localStorage.setItem('auth_user', JSON.stringify(userData));
        })
        .catch(() => {
          logout();
        });
    }
  }, [token]);

  const notify = (message, type = 'info') => {
    setNotification({ message, type, id: Date.now() });
    setTimeout(() => {
      setNotification(prev => (prev && prev.message === message ? null : prev));
    }, 4500);
  };

  const closeNotification = () => setNotification(null);

  // Auth actions
  const login = async (email, password) => {
    try {
      setLoading(true);
      setLoadingMessage('Authenticating credentials...');
      const data = await api.login(email, password);
      setToken(data.access_token);
      setUser(data.user);
      localStorage.setItem('auth_token', data.access_token);
      localStorage.setItem('auth_user', JSON.stringify(data.user));

      notify(`Welcome back, ${data.user.full_name}! (${data.user.role.toUpperCase()})`, 'success');

      if (data.user.role === 'admin') {
        setActiveTab('faculty-mgmt');
      } else if (data.user.role === 'student') {
        setActiveTab('student-dashboard');
      } else {
        setActiveTab('home');
      }
      return data;
    } catch (err) {
      notify(err.message || 'Login failed. Please check credentials.', 'error');
      throw err;
    } finally {
      setLoading(false);
      setLoadingMessage('');
    }
  };

  const logout = () => {
    setToken(null);
    setUser(null);
    localStorage.removeItem('auth_token');
    localStorage.removeItem('auth_user');
    setActiveTab('login');
    notify('You have been logged out successfully.', 'info');
  };

  // Load books for current syllabus
  const loadBooks = async (syllabusId, category = null, search = null) => {
    try {
      setLoading(true);
      const data = await api.getBooks(syllabusId, category, search);
      setBooks(data);
      return data;
    } catch (err) {
      notify(err.message, 'error');
      return [];
    } finally {
      setLoading(false);
    }
  };

  // Load search results
  const loadSearchResults = async (syllabusId, filters = {}) => {
    try {
      setLoading(true);
      const data = await api.getSearchResults(syllabusId, filters);
      setSearchResults(data);
      return data;
    } catch (err) {
      notify(err.message, 'error');
      return [];
    } finally {
      setLoading(false);
    }
  };

  // Load analytics
  const loadAnalytics = async (syllabusId) => {
    try {
      const data = await api.getAnalytics(syllabusId);
      setAnalytics(data);
      return data;
    } catch (err) {
      console.error('Failed to fetch analytics:', err);
      return null;
    }
  };

  // Trigger search across syllabus
  const runLawfulSearch = async (syllabusId) => {
    try {
      setLoading(true);
      setLoadingMessage('Searching lawful repositories (Google Books, Open Library, Crossref, IA)...');
      const res = await api.searchSyllabusBooks(syllabusId);
      notify(res.message || 'Search completed successfully!', 'success');
      await loadSearchResults(syllabusId);
      await loadAnalytics(syllabusId);
      setActiveTab('results');
    } catch (err) {
      notify(err.message || 'Search failed', 'error');
    } finally {
      setLoading(false);
      setLoadingMessage('');
    }
  };

  // Course outcomes & content loaders
  const loadCourseOutcomes = async (syllabusId) => {
    try {
      const data = await api.getCourseOutcomes(syllabusId);
      setCourseOutcomes(data);
      return data;
    } catch (err) {
      console.error('Failed to load course outcomes:', err);
      return [];
    }
  };

  const loadContentFiles = async (syllabusId) => {
    try {
      const data = await api.getContentFiles(syllabusId);
      setContentFiles(data);
      return data;
    } catch (err) {
      console.error('Failed to load content files:', err);
      return [];
    }
  };

  // Student action helpers
  const loadStudentDashboard = async () => {
    try {
      setLoading(true);
      const data = await api.getStudentDashboard();
      setStudentDashboardData(data);
      if (data?.enrolled_courses) {
        setStudentCourses(data.enrolled_courses);
      }
      if (data?.notifications) {
        setStudentNotifications(data.notifications);
      }
      return data;
    } catch (err) {
      notify(err.message || 'Failed to load student dashboard', 'error');
      return null;
    } finally {
      setLoading(false);
    }
  };

  const loadStudentCourses = async () => {
    try {
      setLoading(true);
      const data = await api.getStudentCourses();
      setStudentCourses(data);
      return data;
    } catch (err) {
      notify(err.message || 'Failed to load enrolled courses', 'error');
      return [];
    } finally {
      setLoading(false);
    }
  };

  return (
    <AppContext.Provider
      value={{
        // Auth
        token,
        user,
        role: user?.role || 'guest',
        isAdmin: user?.role === 'admin',
        isFaculty: user?.role === 'faculty',
        isStudent: user?.role === 'student',
        login,
        logout,

        // Navigation
        activeTab,
        setActiveTab,
        currentPath,
        navigate,

        // Syllabus & Books
        currentSyllabus,
        setCurrentSyllabus,
        books,
        setBooks,
        searchResults,
        setSearchResults,
        analytics,
        setAnalytics,

        // Content, Outcomes & Question Paper
        courseOutcomes,
        setCourseOutcomes,
        contentFiles,
        setContentFiles,
        currentQuestionPaper,
        setCurrentQuestionPaper,

        // Student Module State & Actions
        selectedStudentCourseId,
        setSelectedStudentCourseId,
        studentDashboardData,
        setStudentDashboardData,
        studentCourses,
        setStudentCourses,
        studentNotifications,
        setStudentNotifications,
        loadStudentDashboard,
        loadStudentCourses,

        // UI state
        loading,
        setLoading,
        loadingMessage,
        setLoadingMessage,
        notification,
        notify,
        closeNotification,

        // Async action helpers
        loadBooks,
        loadSearchResults,
        loadAnalytics,
        runLawfulSearch,
        loadCourseOutcomes,
        loadContentFiles,
      }}
    >
      {children}
    </AppContext.Provider>
  );
}

export function useApp() {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useApp must be used within an AppProvider');
  }
  return context;
}
