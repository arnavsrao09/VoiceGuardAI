import React, { useState, useEffect } from 'react';
import { apiFetch } from '../lib/api';
import { Key, Plus, Trash2, Copy, Check } from 'lucide-react';

interface ApiKey {
  id: string;
  prefix: string;
  is_active: boolean;
  created_at: string;
}

export default function ApiKeysPage() {
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [newKey, setNewKey] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    fetchKeys();
  }, []);

  const fetchKeys = async () => {
    try {
      const data = await apiFetch('/org/keys');
      setKeys(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateKey = async () => {
    try {
      const data = await apiFetch('/org/keys', { method: 'POST' });
      setNewKey(data.key);
      setKeys([data, ...keys]);
    } catch (err) {
      console.error(err);
    }
  };

  const handleRevokeKey = async (id: string) => {
    if (!confirm('Are you sure you want to revoke this key?')) return;
    try {
      await apiFetch(`/org/keys/${id}`, { method: 'DELETE' });
      setKeys(keys.map(k => k.id === id ? { ...k, is_active: false } : k));
    } catch (err) {
      console.error(err);
    }
  };

  const copyToClipboard = () => {
    if (newKey) {
      navigator.clipboard.writeText(newKey);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="pt-24 pb-12 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-3xl font-bold text-white flex items-center gap-3">
            <Key className="h-8 w-8 text-red-500" />
            API Keys
          </h1>
          <p className="mt-2 text-gray-400">Manage your organization's API keys for B2B integration.</p>
        </div>
        <button
          onClick={handleCreateKey}
          className="flex items-center gap-2 bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded-lg transition-colors"
        >
          <Plus className="h-4 w-4" />
          Generate New Key
        </button>
      </div>

      {newKey && (
        <div className="mb-8 p-4 bg-green-500/10 border border-green-500/20 rounded-lg">
          <h3 className="text-lg font-medium text-green-400 mb-2">New API Key Generated</h3>
          <p className="text-sm text-gray-300 mb-4">
            Please copy this key and store it safely. You will not be able to see it again.
          </p>
          <div className="flex items-center gap-2">
            <code className="flex-1 bg-black/50 p-3 rounded font-mono text-sm text-white break-all">
              {newKey}
            </code>
            <button
              onClick={copyToClipboard}
              className="p-3 bg-white/5 hover:bg-white/10 rounded-lg transition-colors text-white"
            >
              {copied ? <Check className="h-5 w-5 text-green-400" /> : <Copy className="h-5 w-5" />}
            </button>
          </div>
        </div>
      )}

      <div className="glass-panel overflow-hidden">
        <table className="min-w-full divide-y divide-white/10">
          <thead className="bg-white/5">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">Prefix</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">Status</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">Created</th>
              <th className="px-6 py-3 text-right text-xs font-medium text-gray-400 uppercase tracking-wider">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {loading ? (
              <tr>
                <td colSpan={4} className="px-6 py-4 text-center text-gray-400">Loading...</td>
              </tr>
            ) : keys.length === 0 ? (
              <tr>
                <td colSpan={4} className="px-6 py-4 text-center text-gray-400">No API keys found.</td>
              </tr>
            ) : (
              keys.map((key) => (
                <tr key={key.id}>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-mono text-white">
                    {key.prefix}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm">
                    <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${
                      key.is_active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                    }`}>
                      {key.is_active ? 'Active' : 'Revoked'}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-400">
                    {new Date(key.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                    {key.is_active && (
                      <button
                        onClick={() => handleRevokeKey(key.id)}
                        className="text-red-400 hover:text-red-300 transition-colors flex items-center gap-1 ml-auto"
                      >
                        <Trash2 className="h-4 w-4" /> Revoke
                      </button>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
