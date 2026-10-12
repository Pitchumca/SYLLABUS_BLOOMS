import React, { useState } from 'react';
import { X, Plus, BookOpen } from 'lucide-react';
import { api } from '../services/api';
import { useApp } from '../context/AppContext';

export default function AddBookModal({ isOpen, onClose, syllabusId, onBookAdded }) {
  const { notify } = useApp();
  const [formData, setFormData] = useState({
    category: 'Textbook',
    title: '',
    authors: '',
    edition: '',
    publisher: '',
    publication_year: '',
    isbn: '',
  });
  const [submitting, setSubmitting] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!formData.title.trim()) {
      notify('Book title is required', 'error');
      return;
    }

    try {
      setSubmitting(true);
      await api.addBook({
        syllabus_id: syllabusId,
        ...formData,
      });
      notify('New book record added successfully', 'success');
      onBookAdded();
      onClose();
      setFormData({
        category: 'Textbook',
        title: '',
        authors: '',
        edition: '',
        publisher: '',
        publication_year: '',
        isbn: '',
      });
    } catch (err) {
      notify(err.message || 'Failed to add book', 'error');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs animate-fade-in">
      <div className="bg-white rounded-2xl shadow-xl border border-slate-200 w-full max-w-lg overflow-hidden">
        
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 bg-slate-50/50">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-blue-100 flex items-center justify-center text-blue-700">
              <BookOpen className="w-4 h-4" />
            </div>
            <h3 className="font-bold text-slate-900 text-sm">Add Missing Book</h3>
          </div>
          <button 
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4 text-xs">
          
          <div>
            <label className="block font-semibold text-slate-700 mb-1">Book Category *</label>
            <select
              value={formData.category}
              onChange={(e) => setFormData({ ...formData, category: e.target.value })}
              className="w-full px-3 py-2 border border-slate-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:outline-hidden"
            >
              <option value="Textbook">Textbook</option>
              <option value="Reference Book">Reference Book</option>
            </select>
          </div>

          <div>
            <label className="block font-semibold text-slate-700 mb-1">Book Title *</label>
            <input
              type="text"
              required
              placeholder="e.g. Introduction to Algorithms"
              value={formData.title}
              onChange={(e) => setFormData({ ...formData, title: e.target.value })}
              className="w-full px-3 py-2 border border-slate-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:outline-hidden"
            />
          </div>

          <div>
            <label className="block font-semibold text-slate-700 mb-1">Author(s)</label>
            <input
              type="text"
              placeholder="e.g. Thomas H. Cormen, Charles E. Leiserson"
              value={formData.authors}
              onChange={(e) => setFormData({ ...formData, authors: e.target.value })}
              className="w-full px-3 py-2 border border-slate-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:outline-hidden"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block font-semibold text-slate-700 mb-1">Edition</label>
              <input
                type="text"
                placeholder="e.g. 3rd Edition"
                value={formData.edition}
                onChange={(e) => setFormData({ ...formData, edition: e.target.value })}
                className="w-full px-3 py-2 border border-slate-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:outline-hidden"
              />
            </div>
            <div>
              <label className="block font-semibold text-slate-700 mb-1">Publication Year</label>
              <input
                type="text"
                placeholder="e.g. 2009"
                value={formData.publication_year}
                onChange={(e) => setFormData({ ...formData, publication_year: e.target.value })}
                className="w-full px-3 py-2 border border-slate-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:outline-hidden"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block font-semibold text-slate-700 mb-1">Publisher</label>
              <input
                type="text"
                placeholder="e.g. MIT Press / PHI"
                value={formData.publisher}
                onChange={(e) => setFormData({ ...formData, publisher: e.target.value })}
                className="w-full px-3 py-2 border border-slate-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:outline-hidden"
              />
            </div>
            <div>
              <label className="block font-semibold text-slate-700 mb-1">ISBN (ISBN-10 or 13)</label>
              <input
                type="text"
                placeholder="e.g. 978-0262033848"
                value={formData.isbn}
                onChange={(e) => setFormData({ ...formData, isbn: e.target.value })}
                className="w-full px-3 py-2 border border-slate-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:outline-hidden"
              />
            </div>
          </div>

          {/* Buttons */}
          <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-100">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-slate-600 hover:bg-slate-100 rounded-xl font-medium transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl font-semibold shadow-sm transition-all flex items-center gap-1.5"
            >
              <Plus className="w-4 h-4" />
              <span>{submitting ? 'Adding...' : 'Add Book'}</span>
            </button>
          </div>

        </form>

      </div>
    </div>
  );
}
