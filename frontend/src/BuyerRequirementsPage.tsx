import { useState, useEffect } from 'react';
import type {
  BuyerRequirement,
  BuyerRequirementCreate,
  BuyerRequirementUpdate,
} from './lib/buyerService';
import {
  fetchRequirements,
  createRequirement,
  updateRequirement,
  deleteRequirement,
} from './lib/buyerService';

const QUALITIES = ['Any', 'Low', 'Standard', 'Premium'];

interface FieldErrors {
  crop?: string;
  quantity_kg?: string;
  quality?: string;
  budget_per_kg?: string;
}

function validateForm(
  crop: string,
  quantityStr: string,
  quality: string,
  budgetStr: string,
): FieldErrors {
  const errors: FieldErrors = {};
  if (!crop.trim()) errors.crop = 'Crop name is required.';
  const qty = parseFloat(quantityStr);
  if (!quantityStr.trim() || isNaN(qty) || qty <= 0) {
    errors.quantity_kg = 'Enter a quantity greater than 0.';
  }
  if (!quality) errors.quality = 'Select a quality grade.';
  if (budgetStr.trim()) {
    const b = parseFloat(budgetStr);
    if (isNaN(b) || b <= 0) errors.budget_per_kg = 'Budget must be greater than 0.';
  }
  return errors;
}

interface RequirementFormProps {
  initial?: BuyerRequirement | null;
  onSave: (data: BuyerRequirementCreate | BuyerRequirementUpdate) => Promise<void>;
  onCancel: () => void;
  saving: boolean;
  saveError: string | null;
}

function RequirementForm({ initial, onSave, onCancel, saving, saveError }: RequirementFormProps) {
  const [crop, setCrop] = useState(initial?.crop ?? '');
  const [quantity, setQuantity] = useState(initial ? String(initial.quantity_kg) : '');
  const [quality, setQuality] = useState(initial?.quality ?? 'Any');
  const [deliveryState, setDeliveryState] = useState(initial?.delivery_state ?? '');
  const [deliveryDistrict, setDeliveryDistrict] = useState(initial?.delivery_district ?? '');
  const [budget, setBudget] = useState(initial?.budget_per_kg != null ? String(initial.budget_per_kg) : '');
  const [neededBy, setNeededBy] = useState(initial?.needed_by ?? '');
  const [notes, setNotes] = useState(initial?.notes ?? '');
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});

  const inputCls =
    'w-full px-3 py-2.5 rounded-xl border border-gray-200 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none text-sm transition bg-white placeholder:text-gray-300';
  const inputErrCls =
    'w-full px-3 py-2.5 rounded-xl border border-red-300 focus:ring-2 focus:ring-red-400 focus:border-red-400 outline-none text-sm transition bg-white placeholder:text-gray-300';

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const errors = validateForm(crop, quantity, quality, budget);
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) return;

    const payload = {
      crop: crop.trim(),
      quantity_kg: parseFloat(quantity),
      quality,
      delivery_state: deliveryState.trim() || null,
      delivery_district: deliveryDistrict.trim() || null,
      budget_per_kg: budget.trim() ? parseFloat(budget) : null,
      needed_by: neededBy.trim() || null,
      notes: notes.trim() || null,
    };
    await onSave(payload);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label className="block text-xs font-semibold text-gray-600 mb-1">
            Crop / Produce <span className="text-red-400">*</span>
          </label>
          <input
            type="text"
            placeholder="e.g. Tomato"
            value={crop}
            onChange={(e) => { setCrop(e.target.value); setFieldErrors((fe) => ({ ...fe, crop: undefined })); }}
            maxLength={80}
            className={fieldErrors.crop ? inputErrCls : inputCls}
          />
          {fieldErrors.crop && <p className="mt-1 text-xs text-red-600">{fieldErrors.crop}</p>}
        </div>
        <div>
          <label className="block text-xs font-semibold text-gray-600 mb-1">
            Quantity (kg) <span className="text-red-400">*</span>
          </label>
          <input
            type="number"
            placeholder="e.g. 500"
            min="1"
            step="any"
            value={quantity}
            onChange={(e) => { setQuantity(e.target.value); setFieldErrors((fe) => ({ ...fe, quantity_kg: undefined })); }}
            className={fieldErrors.quantity_kg ? inputErrCls : inputCls}
          />
          {fieldErrors.quantity_kg && <p className="mt-1 text-xs text-red-600">{fieldErrors.quantity_kg}</p>}
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label className="block text-xs font-semibold text-gray-600 mb-1">
            Quality Grade <span className="text-red-400">*</span>
          </label>
          <select
            value={quality}
            onChange={(e) => { setQuality(e.target.value); setFieldErrors((fe) => ({ ...fe, quality: undefined })); }}
            className={fieldErrors.quality ? inputErrCls : inputCls}
          >
            {QUALITIES.map((q) => <option key={q} value={q}>{q}</option>)}
          </select>
          {fieldErrors.quality && <p className="mt-1 text-xs text-red-600">{fieldErrors.quality}</p>}
        </div>
        <div>
          <label className="block text-xs font-semibold text-gray-600 mb-1">
            Max Budget (₹/kg)
          </label>
          <input
            type="number"
            placeholder="e.g. 25"
            min="0.01"
            step="any"
            value={budget}
            onChange={(e) => { setBudget(e.target.value); setFieldErrors((fe) => ({ ...fe, budget_per_kg: undefined })); }}
            className={fieldErrors.budget_per_kg ? inputErrCls : inputCls}
          />
          {fieldErrors.budget_per_kg && <p className="mt-1 text-xs text-red-600">{fieldErrors.budget_per_kg}</p>}
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label className="block text-xs font-semibold text-gray-600 mb-1">Delivery State</label>
          <input
            type="text"
            placeholder="e.g. Andhra Pradesh"
            value={deliveryState}
            onChange={(e) => setDeliveryState(e.target.value)}
            maxLength={80}
            className={inputCls}
          />
        </div>
        <div>
          <label className="block text-xs font-semibold text-gray-600 mb-1">Delivery District</label>
          <input
            type="text"
            placeholder="e.g. Guntur"
            value={deliveryDistrict}
            onChange={(e) => setDeliveryDistrict(e.target.value)}
            maxLength={80}
            className={inputCls}
          />
        </div>
      </div>

      <div>
        <label className="block text-xs font-semibold text-gray-600 mb-1">Needed By</label>
        <input
          type="date"
          value={neededBy}
          onChange={(e) => setNeededBy(e.target.value)}
          className={inputCls}
        />
      </div>

      <div>
        <label className="block text-xs font-semibold text-gray-600 mb-1">Notes</label>
        <textarea
          placeholder="Any additional requirements or preferences…"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={3}
          maxLength={500}
          className={inputCls}
        />
      </div>

      {saveError && (
        <div className="px-4 py-3 rounded-xl bg-red-50 border border-red-200 text-sm text-red-700">
          {saveError}
        </div>
      )}

      <div className="flex gap-3">
        <button
          type="submit"
          disabled={saving}
          className="flex-1 py-2.5 rounded-xl font-semibold text-sm text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50 transition"
        >
          {saving ? 'Saving…' : initial ? 'Update Requirement' : 'Post Requirement'}
        </button>
        <button
          type="button"
          onClick={onCancel}
          disabled={saving}
          className="px-5 py-2.5 rounded-xl font-semibold text-sm text-gray-600 border border-gray-200 hover:bg-gray-50 disabled:opacity-50 transition"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}

const QUALITY_COLOR: Record<string, string> = {
  Premium: 'bg-purple-100 text-purple-700',
  Standard: 'bg-blue-100 text-blue-700',
  Low: 'bg-gray-100 text-gray-600',
  Any: 'bg-green-100 text-green-700',
};

interface BuyerRequirementsPageProps {
  onBack: () => void;
}

export default function BuyerRequirementsPage({ onBack }: BuyerRequirementsPageProps) {
  const [requirements, setRequirements] = useState<BuyerRequirement[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const [deletingId, setDeletingId] = useState<string | null>(null);

  useEffect(() => {
    loadRequirements();
  }, []);

  async function loadRequirements() {
    setLoading(true);
    setLoadError(null);
    try {
      const reqs = await fetchRequirements();
      setRequirements(reqs);
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : 'Failed to load requirements.');
    } finally {
      setLoading(false);
    }
  }

  async function handleCreate(data: BuyerRequirementCreate | BuyerRequirementUpdate) {
    setSaving(true);
    setSaveError(null);
    try {
      const created = await createRequirement(data as BuyerRequirementCreate);
      setRequirements((prev) => [created, ...prev]);
      setShowForm(false);
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Failed to save requirement.');
    } finally {
      setSaving(false);
    }
  }

  async function handleUpdate(id: string, data: BuyerRequirementCreate | BuyerRequirementUpdate) {
    setSaving(true);
    setSaveError(null);
    try {
      const updated = await updateRequirement(id, data);
      setRequirements((prev) => prev.map((r) => (r.id === id ? updated : r)));
      setEditingId(null);
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Failed to update requirement.');
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id: string) {
    setDeletingId(id);
    try {
      await deleteRequirement(id);
      setRequirements((prev) => prev.filter((r) => r.id !== id));
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : 'Failed to delete requirement.');
    } finally {
      setDeletingId(null);
    }
  }

  async function handleToggleActive(req: BuyerRequirement) {
    try {
      const updated = await updateRequirement(req.id, { is_active: !req.is_active });
      setRequirements((prev) => prev.map((r) => (r.id === req.id ? updated : r)));
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : 'Failed to update requirement.');
    }
  }

  return (
    <div className="w-full max-w-2xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <button
          onClick={onBack}
          className="text-sm text-gray-400 hover:text-gray-700 transition flex items-center gap-1"
        >
          ← Back
        </button>
        <div className="flex-1">
          <h1 className="text-2xl font-bold text-gray-900">My Requirements</h1>
          <p className="text-sm text-gray-400 mt-0.5">Post what you need — farmers will find you</p>
        </div>
        {!showForm && editingId === null && (
          <button
            onClick={() => { setShowForm(true); setSaveError(null); }}
            className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold transition"
          >
            + Post Requirement
          </button>
        )}
      </div>

      {/* New requirement form */}
      {showForm && (
        <div className="bg-white rounded-2xl border border-blue-100 shadow-sm p-6">
          <h2 className="text-sm font-bold text-gray-700 mb-4">New Procurement Requirement</h2>
          <RequirementForm
            onSave={handleCreate}
            onCancel={() => { setShowForm(false); setSaveError(null); }}
            saving={saving}
            saveError={saveError}
          />
        </div>
      )}

      {/* Load error */}
      {loadError && (
        <div className="px-4 py-3 rounded-xl bg-red-50 border border-red-200 text-sm text-red-700">
          {loadError}
        </div>
      )}

      {/* Loading */}
      {loading ? (
        <div className="flex items-center justify-center py-16 gap-3 text-gray-400">
          <span className="inline-block w-5 h-5 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
          <span className="text-sm">Loading requirements…</span>
        </div>
      ) : requirements.length === 0 && !showForm ? (
        /* Empty state */
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-10 text-center">
          <div className="text-4xl mb-3">📋</div>
          <h3 className="font-bold text-gray-800 mb-1">No requirements yet</h3>
          <p className="text-sm text-gray-500 mb-4">
            Post your first procurement need so farmers know what you're looking for.
          </p>
          <button
            onClick={() => { setShowForm(true); setSaveError(null); }}
            className="px-5 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold transition"
          >
            Post Your First Requirement
          </button>
        </div>
      ) : (
        /* Requirements list */
        <div className="space-y-4">
          {requirements.map((req) => (
            <div
              key={req.id}
              className={`bg-white rounded-2xl border shadow-sm overflow-hidden transition ${
                req.is_active ? 'border-gray-100' : 'border-gray-100 opacity-60'
              }`}
            >
              {editingId === req.id ? (
                <div className="p-6">
                  <h3 className="text-sm font-bold text-gray-700 mb-4">Edit Requirement</h3>
                  <RequirementForm
                    initial={req}
                    onSave={(data) => handleUpdate(req.id, data)}
                    onCancel={() => { setEditingId(null); setSaveError(null); }}
                    saving={saving}
                    saveError={saveError}
                  />
                </div>
              ) : (
                <div className="px-5 py-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap mb-2">
                        <h3 className="font-bold text-gray-900 text-base">{req.crop}</h3>
                        <span className={`text-xs px-2.5 py-0.5 rounded-full font-semibold ${QUALITY_COLOR[req.quality] ?? 'bg-gray-100 text-gray-600'}`}>
                          {req.quality}
                        </span>
                        {!req.is_active && (
                          <span className="text-xs px-2.5 py-0.5 rounded-full bg-gray-100 text-gray-400 font-medium">
                            Inactive
                          </span>
                        )}
                      </div>

                      <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-gray-600">
                        <span className="font-medium">{req.quantity_kg.toLocaleString()} kg</span>
                        {req.budget_per_kg != null && (
                          <span>Budget: ₹{req.budget_per_kg}/kg</span>
                        )}
                        {(req.delivery_state || req.delivery_district) && (
                          <span>
                            📍 {[req.delivery_district, req.delivery_state].filter(Boolean).join(', ')}
                          </span>
                        )}
                        {req.needed_by && (
                          <span>🗓 {new Date(req.needed_by).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}</span>
                        )}
                      </div>

                      {req.notes && (
                        <p className="mt-2 text-xs text-gray-400 line-clamp-2">{req.notes}</p>
                      )}

                      <p className="mt-1.5 text-xs text-gray-300">
                        Posted {new Date(req.created_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}
                      </p>
                    </div>

                    {/* Actions */}
                    <div className="flex items-center gap-1.5 flex-shrink-0">
                      <button
                        onClick={() => handleToggleActive(req)}
                        className="text-xs px-2.5 py-1.5 rounded-lg border border-gray-200 text-gray-500 hover:bg-gray-50 transition font-medium"
                        title={req.is_active ? 'Mark inactive' : 'Mark active'}
                      >
                        {req.is_active ? 'Deactivate' : 'Activate'}
                      </button>
                      <button
                        onClick={() => { setEditingId(req.id); setSaveError(null); }}
                        className="text-xs px-2.5 py-1.5 rounded-lg border border-gray-200 text-gray-500 hover:bg-blue-50 hover:text-blue-600 hover:border-blue-200 transition font-medium"
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => handleDelete(req.id)}
                        disabled={deletingId === req.id}
                        className="text-xs px-2.5 py-1.5 rounded-lg border border-gray-200 text-gray-400 hover:bg-red-50 hover:text-red-600 hover:border-red-200 disabled:opacity-40 transition font-medium"
                      >
                        {deletingId === req.id ? '…' : 'Delete'}
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
