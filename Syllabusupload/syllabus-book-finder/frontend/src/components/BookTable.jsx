import React, { useState } from 'react';
import { 
  Check, 
  Edit3, 
  Trash2, 
  Save, 
  X, 
  AlertCircle, 
  Layers, 
  CheckCircle2 
} from 'lucide-react';
import { api } from '../services/api';
import { useApp } from '../context/AppContext';

export default function BookTable({ books, onRefresh, onOpenMerge }) {
  const { notify } = useApp();
  const [editingId, setEditingId] = useState(null);
  const [editForm, setEditForm] = useState({});

  const startEditing = (book) => {
    setEditingId(book.id);
    setEditForm({
      category: book.category,
      title: book.title,
      authors: book.authors || '',
      edition: book.edition || '',
      publisher: book.publisher || '',
      publication_year: book.publication_year || '',
      isbn: book.isbn || '',
    });
  };

  const cancelEditing = () => {
    setEditingId(null);
    setEditForm({});
  };

  const saveEditing = async (bookId) => {
    try {
      await api.updateBook(bookId, { ...editForm, is_reviewed: true });
      notify('Book details updated successfully', 'success');
      setEditingId(null);
      onRefresh();
    } catch (err) {
      notify(err.message || 'Failed to update book', 'error');
    }
  };

  const handleDelete = async (bookId) => {
    if (!window.confirm('Are you sure you want to remove this book from the syllabus?')) return;
    try {
      await api.deleteBook(bookId);
      notify('Book record deleted', 'info');
      onRefresh();
    } catch (err) {
      notify(err.message || 'Failed to delete book', 'error');
    }
  };

  const toggleCategory = async (book) => {
    const newCategory = book.category === 'Textbook' ? 'Reference Book' : 'Textbook';
    try {
      await api.updateBook(book.id, { category: newCategory });
      onRefresh();
    } catch (err) {
      notify('Failed to switch category', 'error');
    }
  };

  const toggleReviewed = async (book) => {
    try {
      await api.updateBook(book.id, { is_reviewed: !book.is_reviewed });
      onRefresh();
    } catch (err) {
      notify('Failed to update review status', 'error');
    }
  };

  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-xs overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 uppercase font-semibold text-[11px] tracking-wider">
            <tr>
              <th className="py-3.5 px-4 w-12 text-center">Status</th>
              <th className="py-3.5 px-4 w-32">Category</th>
              <th className="py-3.5 px-4 min-w-[220px]">Title</th>
              <th className="py-3.5 px-4 min-w-[160px]">Author(s)</th>
              <th className="py-3.5 px-4 w-28">Edition</th>
              <th className="py-3.5 px-4 min-w-[140px]">Publisher</th>
              <th className="py-3.5 px-4 w-20 text-center">Year</th>
              <th className="py-3.5 px-4 w-32">ISBN</th>
              <th className="py-3.5 px-4 w-28 text-center">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {books.map((book, idx) => {
              const isEditing = editingId === book.id;

              return (
                <tr 
                  key={book.id} 
                  className={`hover:bg-slate-50/80 transition-colors ${
                    book.is_duplicate ? 'bg-amber-50/40' : ''
                  }`}
                >
                  {/* Status Checkbox */}
                  <td className="py-3 px-4 text-center">
                    <button
                      onClick={() => toggleReviewed(book)}
                      title={book.is_reviewed ? 'Reviewed & Confirmed' : 'Click to confirm review'}
                      className={`p-1 rounded-md transition-colors ${
                        book.is_reviewed
                          ? 'text-emerald-600 hover:text-emerald-700 bg-emerald-50'
                          : 'text-slate-300 hover:text-slate-500'
                      }`}
                    >
                      <CheckCircle2 className="w-5 h-5" />
                    </button>
                  </td>

                  {/* Category Toggle */}
                  <td className="py-3 px-4">
                    {isEditing ? (
                      <select
                        value={editForm.category}
                        onChange={(e) => setEditForm({ ...editForm, category: e.target.value })}
                        className="w-full text-xs p-1.5 border border-slate-300 rounded-lg focus:ring-1 focus:ring-blue-500"
                      >
                        <option value="Textbook">Textbook</option>
                        <option value="Reference Book">Reference Book</option>
                      </select>
                    ) : (
                      <button
                        onClick={() => toggleCategory(book)}
                        className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold uppercase tracking-wider transition-colors ${
                          book.category === 'Textbook'
                            ? 'bg-blue-100 text-blue-800 hover:bg-blue-200'
                            : 'bg-purple-100 text-purple-800 hover:bg-purple-200'
                        }`}
                        title="Click to switch category"
                      >
                        {book.category}
                      </button>
                    )}
                  </td>

                  {/* Title */}
                  <td className="py-3 px-4 font-medium text-slate-900">
                    {isEditing ? (
                      <input
                        type="text"
                        value={editForm.title}
                        onChange={(e) => setEditForm({ ...editForm, title: e.target.value })}
                        className="w-full text-xs p-1.5 border border-slate-300 rounded-lg focus:ring-1 focus:ring-blue-500"
                      />
                    ) : (
                      <div className="flex items-center gap-1.5">
                        <span className="font-semibold text-slate-800 leading-tight">{book.title}</span>
                        {book.is_duplicate && (
                          <span 
                            onClick={() => onOpenMerge(book)}
                            className="shrink-0 cursor-pointer inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] bg-amber-100 text-amber-800 hover:bg-amber-200 border border-amber-300"
                            title="Potential duplicate detected. Click to merge."
                          >
                            <AlertCircle className="w-3 h-3 text-amber-700" />
                            <span>Duplicate</span>
                          </span>
                        )}
                      </div>
                    )}
                  </td>

                  {/* Authors */}
                  <td className="py-3 px-4 text-slate-600">
                    {isEditing ? (
                      <input
                        type="text"
                        value={editForm.authors}
                        onChange={(e) => setEditForm({ ...editForm, authors: e.target.value })}
                        className="w-full text-xs p-1.5 border border-slate-300 rounded-lg focus:ring-1 focus:ring-blue-500"
                      />
                    ) : (
                      <span>{book.authors || '—'}</span>
                    )}
                  </td>

                  {/* Edition */}
                  <td className="py-3 px-4 text-slate-600">
                    {isEditing ? (
                      <input
                        type="text"
                        value={editForm.edition}
                        onChange={(e) => setEditForm({ ...editForm, edition: e.target.value })}
                        className="w-full text-xs p-1.5 border border-slate-300 rounded-lg focus:ring-1 focus:ring-blue-500"
                      />
                    ) : (
                      <span>{book.edition || '—'}</span>
                    )}
                  </td>

                  {/* Publisher */}
                  <td className="py-3 px-4 text-slate-600">
                    {isEditing ? (
                      <input
                        type="text"
                        value={editForm.publisher}
                        onChange={(e) => setEditForm({ ...editForm, publisher: e.target.value })}
                        className="w-full text-xs p-1.5 border border-slate-300 rounded-lg focus:ring-1 focus:ring-blue-500"
                      />
                    ) : (
                      <span>{book.publisher || '—'}</span>
                    )}
                  </td>

                  {/* Publication Year */}
                  <td className="py-3 px-4 text-center text-slate-600 font-mono">
                    {isEditing ? (
                      <input
                        type="text"
                        value={editForm.publication_year}
                        onChange={(e) => setEditForm({ ...editForm, publication_year: e.target.value })}
                        className="w-full text-xs p-1.5 border border-slate-300 rounded-lg text-center focus:ring-1 focus:ring-blue-500"
                      />
                    ) : (
                      <span>{book.publication_year || '—'}</span>
                    )}
                  </td>

                  {/* ISBN */}
                  <td className="py-3 px-4 text-slate-600 font-mono text-[11px]">
                    {isEditing ? (
                      <input
                        type="text"
                        value={editForm.isbn}
                        onChange={(e) => setEditForm({ ...editForm, isbn: e.target.value })}
                        className="w-full text-xs p-1.5 border border-slate-300 rounded-lg focus:ring-1 focus:ring-blue-500"
                      />
                    ) : (
                      <span>{book.isbn || '—'}</span>
                    )}
                  </td>

                  {/* Action Buttons */}
                  <td className="py-3 px-4 text-center">
                    {isEditing ? (
                      <div className="flex items-center justify-center gap-1">
                        <button
                          onClick={() => saveEditing(book.id)}
                          className="p-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg shadow-xs"
                          title="Save Changes"
                        >
                          <Save className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={cancelEditing}
                          className="p-1.5 bg-slate-200 hover:bg-slate-300 text-slate-700 rounded-lg"
                          title="Cancel"
                        >
                          <X className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    ) : (
                      <div className="flex items-center justify-center gap-1">
                        <button
                          onClick={() => startEditing(book)}
                          className="p-1.5 text-slate-500 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                          title="Edit Details"
                        >
                          <Edit3 className="w-3.5 h-3.5" />
                        </button>
                        {book.is_duplicate && (
                          <button
                            onClick={() => onOpenMerge(book)}
                            className="p-1.5 text-amber-600 hover:text-amber-700 hover:bg-amber-50 rounded-lg transition-colors"
                            title="Merge Records"
                          >
                            <Layers className="w-3.5 h-3.5" />
                          </button>
                        )}
                        <button
                          onClick={() => handleDelete(book.id)}
                          className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors"
                          title="Delete Record"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
