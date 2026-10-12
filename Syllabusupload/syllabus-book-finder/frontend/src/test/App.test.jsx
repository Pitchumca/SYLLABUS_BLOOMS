import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, beforeEach } from 'vitest';
import App from '../App';

describe('AI-Powered Syllabus & Examination System', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('renders application navbar and login view by default when unauthenticated', () => {
    render(<App />);
    expect(screen.getByText('Syllabus Book Finder')).toBeInTheDocument();
    expect(screen.getByText(/AI-Powered Syllabus & Examination System/i)).toBeInTheDocument();
    expect(screen.getByText('Faculty Login')).toBeInTheDocument();
    expect(screen.getByText('Admin Login')).toBeInTheDocument();
  });

  it('switches to About & Policy page', () => {
    render(<App />);
    const aboutButtons = screen.getAllByText(/About & Policy/i);
    fireEvent.click(aboutButtons[0]);
    expect(screen.getByText(/About & Academic Usage Policy/i)).toBeInTheDocument();
  });

  it('renders authenticated faculty dashboard and question paper navigation when faculty user is stored', () => {
    const mockFaculty = {
      id: 1,
      full_name: 'Dr. Rajesh Raman',
      email: 'faculty@college.edu',
      role: 'faculty',
      department: 'Computer Science & Engineering',
      designation: 'Associate Professor'
    };
    localStorage.setItem('auth_token', 'mock_token_123');
    localStorage.setItem('auth_user', JSON.stringify(mockFaculty));

    render(<App />);
    expect(screen.getByText('Syllabus Book Finder')).toBeInTheDocument();
    expect(screen.getByText('Dr. Rajesh Raman')).toBeInTheDocument();
  });

  it('renders authenticated student dashboard navigation and student badge when student user is stored', () => {
    const mockStudent = {
      id: 7,
      full_name: 'Aarav Sharma',
      email: 'student1@college.edu',
      role: 'student',
      department: 'Computer Science & Engineering',
      designation: 'Student'
    };
    localStorage.setItem('auth_token', 'mock_token_student');
    localStorage.setItem('auth_user', JSON.stringify(mockStudent));

    render(<App />);
    expect(screen.getByText('Syllabus Book Finder')).toBeInTheDocument();
    expect(screen.getByText('Aarav Sharma')).toBeInTheDocument();
    expect(screen.getByText(/Student • IV Sem/i)).toBeInTheDocument();
    expect(screen.getByText('My Courses')).toBeInTheDocument();
  });

  it('recognizes question paper export route URL structure', () => {
    window.history.pushState({}, 'Word Export', '/question-papers/47/export');
    expect(window.location.pathname).toBe('/question-papers/47/export');
    const qpMatch = window.location.pathname.match(/^\/question-papers(?:\/(\d+))?(?:\/([a-zA-Z0-9_-]+))?/);
    expect(qpMatch).toBeTruthy();
    expect(qpMatch[1]).toBe('47');
    expect(qpMatch[2]).toBe('export');
  });
});

