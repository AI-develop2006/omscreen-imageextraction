import { useState, useRef, useEffect, useCallback } from 'react';
import logo from './assets/omscreen logo.png';

function App() {
  const [activeTab, setActiveTab] = useState('converter'); // 'converter', 'history', or 'preview'
  const [history, setHistory] = useState([]);
  const [isFetchingHistory, setIsFetchingHistory] = useState(false);

  const [files, setFiles] = useState([]);
  const [previews, setPreviews] = useState([]);
  const [apiKey, setApiKey] = useState('');
  const [isDragActive, setIsDragActive] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [loadingMessage, setLoadingMessage] = useState('');
  const fileInputRef = useRef(null);

  // New states for preview/edit
  const [previewData, setPreviewData] = useState(null);
  const [previewId, setPreviewId] = useState(null);
  const [previewFilename, setPreviewFilename] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [originalTab, setOriginalTab] = useState('converter');

  // Auth states
  const [token, setToken] = useState(localStorage.getItem('token') || '');
  const [isAuthView, setIsAuthView] = useState(!localStorage.getItem('token'));
  const [authMode, setAuthMode] = useState('login'); // 'login' or 'signup'
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);

  const apiUrl = import.meta.env.VITE_API_URL || '';

  const loadingMessages = [
    "Analyzing image structure...",
    "Extracting text from rows...",
    "Identifying columns...",
    "Formatting table data...",
    "Processing batch files...",
    "Almost there..."
  ];

  const fetchHistory = useCallback(async () => {
    if (!token) return;
    setIsFetchingHistory(true);
    try {
      const response = await fetch(`${apiUrl}/api/history`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (response.ok) {
        const data = await response.json();
        setHistory(data);
      } else if (response.status === 401) {
        handleLogout();
      }
    } catch (err) {
      console.error("Failed to fetch history:", err);
    } finally {
      setIsFetchingHistory(false);
    }
  }, [token, apiUrl]);

  useEffect(() => {
    let interval;
    if (isLoading) {
      let index = 0;
      setLoadingMessage(loadingMessages[0]);
      interval = setInterval(() => {
        index = (index + 1) % loadingMessages.length;
        setLoadingMessage(loadingMessages[index]);
      }, 2500);
    } else {
      setLoadingMessage('');
    }
    return () => clearInterval(interval);
  }, [isLoading]);

  useEffect(() => {
    if (activeTab === 'history' && token) {
      fetchHistory();
    }
  }, [activeTab, token, fetchHistory]);

  const handleLogin = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);
    try {
      const formData = new URLSearchParams();
      formData.append('username', username);
      formData.append('password', password);

      const response = await fetch(`${apiUrl}/api/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: formData,
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || 'Login failed');
      }

      const data = await response.json();
      localStorage.setItem('token', data.access_token);
      setToken(data.access_token);
      setIsAuthView(false);
      setUsername('');
      setPassword('');
      setActiveTab('converter');
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSignup = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);
    try {
      const response = await fetch(`${apiUrl}/api/signup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || 'Signup failed');
      }

      alert("Account created! Please login.");
      setAuthMode('login');
      setPassword('');
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    setToken('');
    setIsAuthView(true);
    setHistory([]);
    setPreviewData(null);
  };

  const processFiles = (selectedFiles) => {
    const newFiles = Array.from(selectedFiles).filter(file => file.type.startsWith('image/'));

    if (files.length + newFiles.length > 10) {
      setError('Maximum 10 files allowed.');
      return;
    }

    setError(null);
    const updatedFiles = [...files, ...newFiles];
    setFiles(updatedFiles);

    newFiles.forEach(file => {
      const reader = new FileReader();
      reader.onload = (e) => setPreviews(prev => [...prev, e.target.result]);
      reader.readAsDataURL(file);
    });
  };

  const removeFile = (index) => {
    setFiles(prev => prev.filter((_, i) => i !== index));
    setPreviews(prev => prev.filter((_, i) => i !== index));
  };

  const handleUpload = async () => {
    if (files.length === 0) { setError('Please select at least one file.'); return; }
    setIsLoading(true); setError(null);
    const formData = new FormData();
    files.forEach(file => {
      formData.append('files', file);
    });
    if (apiKey) formData.append('api_key', apiKey);

    try {
      const response = await fetch(`${apiUrl}/api/convert`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
        body: formData,
      });

      if (!response.ok) {
        const errData = await response.json();
        if (response.status === 401) handleLogout();
        if (response.status === 429) {
          throw new Error("Rate limit exceeded. Please wait about a minute before trying again.");
        }
        throw new Error(errData.detail || 'Conversion failed.');
      }

      const result = await response.json();
      setPreviewId(result.id);
      setPreviewData(result.data);
      setPreviewFilename(result.filename);
      setOriginalTab('converter');
      setActiveTab('preview');
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleViewPreview = async (fileId) => {
    setIsLoading(true);
    try {
      const response = await fetch(`${apiUrl}/api/preview/${fileId}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (!response.ok) {
        if (response.status === 401) handleLogout();
        throw new Error("Failed to load preview");
      }

      const result = await response.json();
      setPreviewId(result.id);
      setPreviewData(result.data);
      setPreviewFilename(result.filename);
      setOriginalTab('history');
      setActiveTab('preview');
    } catch (err) {
      alert("Error: " + err.message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCellChange = (rowIndex, key, newValue) => {
    const newData = [...previewData];
    newData[rowIndex][key] = newValue;
    setPreviewData(newData);
  };

  const handleSave = async () => {
    if (!window.confirm("Save changes to history?")) return;
    setIsSaving(true);
    try {
      const response = await fetch(`${apiUrl}/api/save/${previewId}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ data: previewData }),
      });
      if (!response.ok) throw new Error("Save failed");
      alert("Saved!");
    } catch (err) {
      alert(err.message);
    } finally {
      setIsSaving(false);
    }
  };

  const handleDownload = async () => {
    try {
      const response = await fetch(`${apiUrl}/api/download/${previewId}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (!response.ok) throw new Error("Download failed");
      const blob = await response.blob();
      const downloadUrl = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = downloadUrl;
      link.download = `converted_${previewFilename.split('.')[0]}.xlsx`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(downloadUrl);
    } catch (err) {
      alert(err.message);
    }
  };

  if (isAuthView) {
    return (
      <div className="min-h-screen flex items-center justify-center p-6 relative overflow-hidden">
        <div className="bg-mesh"></div>

        <div className="glass-panel w-full max-w-md p-10 rounded-[2.5rem] z-10 animate-in fade-in slide-in-from-bottom-8 duration-700">
          <div className="flex flex-col items-center mb-8">
            <div className="relative mb-6">
              <div className="absolute inset-0 bg-orange-500/30 blur-3xl rounded-full scale-150 animate-pulse"></div>
              <img src={logo} alt="Om Screen Printing Logo" className="h-28 w-auto relative z-10 logo-glow" />
            </div>
            <h2 className="text-4xl font-black text-gradient tracking-tight text-center">
              Om Screen Printing <span className="text-xs font-bold text-slate-500 opacity-50 ml-1 italic">v1.0</span>
            </h2>
            <p className="text-slate-400 mt-2 font-semibold tracking-[0.2em] uppercase text-sm">Data Extraction System</p>
          </div>

          <div className="h-[1px] w-full bg-gradient-to-r from-transparent via-slate-700 to-transparent mb-8"></div>

          <form onSubmit={authMode === 'login' ? handleLogin : handleSignup} className="space-y-5">
            <div>
              <label className="block text-xs font-bold text-slate-500 uppercase tracking-widest mb-2 ml-1">Username</label>
              <input
                type="text" required value={username} onChange={e => setUsername(e.target.value)}
                className="w-full bg-slate-900/50 border border-slate-800 rounded-2xl px-5 py-4 focus:ring-2 focus:ring-orange-500/50 focus:border-orange-500/50 outline-none transition-all placeholder-slate-600 text-slate-200"
                placeholder="Enter your username"
              />
            </div>
            <div>
              <label className="block text-xs font-bold text-slate-500 uppercase tracking-widest mb-2 ml-1">Password</label>
              <div className="relative">
                <input
                  type={showPassword ? "text" : "password"} required value={password} onChange={e => setPassword(e.target.value)}
                  className="w-full bg-slate-900/50 border border-slate-800 rounded-2xl px-5 py-4 focus:ring-2 focus:ring-orange-500/50 focus:border-orange-500/50 outline-none transition-all pr-14 text-slate-200"
                  placeholder="••••••••"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-600 hover:text-orange-400 transition-colors p-2"
                >
                  {showPassword ? (
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l18 18" />
                    </svg>
                  ) : (
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                    </svg>
                  )}
                </button>
              </div>
            </div>

            {error && <div className="bg-red-500/10 border border-red-500/20 text-red-400 text-sm py-3 px-4 rounded-xl text-center">{error}</div>}

            <button
              type="submit" disabled={isLoading}
              className="w-full btn-primary font-bold py-4 rounded-2xl shadow-xl text-white text-lg mt-4"
            >
              {isLoading ? 'Processing...' : (authMode === 'login' ? 'Login' : 'Sign Up')}
            </button>
          </form>

          <p className="text-center text-sm text-slate-500 mt-8">
            {authMode === 'login' ? "New to the system?" : "Already have an account?"}
            <button onClick={() => setAuthMode(authMode === 'login' ? 'signup' : 'login')} className="ml-2 text-orange-400 font-bold hover:text-orange-300 transition-colors">
              {authMode === 'login' ? 'Create Account' : 'Login'}
            </button>
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-start p-6 relative overflow-hidden">
      <div className="bg-mesh"></div>

      <div className="w-full max-w-6xl z-10 mt-4">
        <header className="flex justify-between items-center mb-12 glass-panel px-8 py-4 rounded-3xl">
          <div className="flex items-center space-x-4">
            <div className="relative">
              <div className="absolute inset-0 bg-orange-500/20 blur-xl rounded-full scale-125"></div>
              <img src={logo} alt="Om Logo" className="h-12 w-auto relative z-10" />
            </div>
            <div>
              <h1 className="text-2xl font-black text-gradient uppercase tracking-tight">
                Om Screen Printing <span className="text-[10px] font-bold text-slate-500 opacity-50 ml-1 lowercase italic">v1.0</span>
              </h1>
              <p className="text-[10px] text-slate-500 font-bold tracking-[0.3em] uppercase opacity-80">Data Extraction</p>
            </div>
          </div>

          <div className="flex items-center space-x-6">
            <nav className="flex bg-slate-900/50 p-1 rounded-2xl border border-slate-800">
              <button onClick={() => { setActiveTab('converter'); setPreviewData(null); }} className={`px-6 py-2 rounded-xl text-sm font-bold transition-all ${activeTab === 'converter' ? 'bg-orange-500 text-white shadow-lg' : 'text-slate-400 hover:text-slate-200'}`}>Converter</button>
              <button onClick={() => { setActiveTab('history'); setPreviewData(null); }} className={`px-6 py-2 rounded-xl text-sm font-bold transition-all ${activeTab === 'history' ? 'bg-orange-500 text-white shadow-lg' : 'text-slate-400 hover:text-slate-200'}`}>History</button>
            </nav>
            <div className="h-8 w-[1px] bg-slate-800"></div>
            <button onClick={handleLogout} className="text-slate-400 hover:text-red-400 transition-colors">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
              </svg>
            </button>
          </div>
        </header>

        <main className="animate-in fade-in slide-in-from-bottom-4 duration-700">
          {activeTab === 'converter' && !previewData && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-10 items-start">
              <div className="space-y-8">
                <div>
                  <h2 className="text-5xl font-black text-white leading-tight mb-4">Digitize your records <br /> <span className="text-gradient">instantly.</span></h2>
                  <p className="text-slate-400 text-lg leading-relaxed max-w-lg">Advanced AI-powered extraction for batch handwritten tables. Upload up to 10 images at once.</p>
                </div>

                <div className="glass-panel rounded-3xl p-6">
                  <label className="block text-xs font-bold text-slate-500 uppercase tracking-widest mb-3 ml-1">Gemini API Key (Optional)</label>
                  <input type="password" value={apiKey} onChange={e => setApiKey(e.target.value)} className="w-full bg-slate-900/50 border border-slate-800 rounded-2xl px-5 py-4 text-white focus:ring-2 focus:ring-orange-500/50 outline-none transition-all" placeholder="Enter custom API key for higher limits..." />
                </div>
              </div>

              <div className="glass-panel rounded-[2rem] p-4">
                <div
                  className={`border-2 border-dashed rounded-[1.5rem] p-6 flex flex-col items-center justify-center transition-all min-h-[300px] cursor-pointer ${isDragActive ? 'border-orange-500 bg-orange-500/10' : 'border-slate-800 bg-slate-900/30 hover:bg-slate-900/50'}`}
                  onDragOver={e => { e.preventDefault(); setIsDragActive(true); }} onDragLeave={() => setIsDragActive(false)} onDrop={e => { e.preventDefault(); setIsDragActive(false); processFiles(e.dataTransfer.files); }} onClick={() => fileInputRef.current?.click()}
                >
                  <input type="file" ref={fileInputRef} className="hidden" accept="image/*" multiple onChange={e => processFiles(e.target.files)} />

                  {previews.length > 0 ? (
                    <div className="grid grid-cols-3 sm:grid-cols-4 gap-4 w-full">
                      {previews.map((src, i) => (
                        <div key={i} className="relative group aspect-square">
                          <img src={src} alt={`Preview ${i}`} className="w-full h-full object-cover rounded-xl border border-slate-700 shadow-md" />
                          <button onClick={e => { e.stopPropagation(); removeFile(i); }} className="absolute -top-2 -right-2 bg-red-500 text-white p-1.5 rounded-full shadow-lg opacity-0 group-hover:opacity-100 transition-opacity">
                            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
                          </button>
                        </div>
                      ))}
                      {previews.length < 10 && (
                        <div className="flex items-center justify-center aspect-square border-2 border-dashed border-slate-700 rounded-xl hover:border-orange-500/50 transition-colors">
                          <svg className="h-8 w-8 text-slate-700" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" /></svg>
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="text-center group">
                      <div className="bg-slate-800/80 rounded-3xl p-6 inline-block mb-6 text-orange-500 group-hover:scale-110 transition-transform duration-500 ring-1 ring-slate-700/50">
                        <svg className="h-16 w-16" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
                      </div>
                      <h3 className="text-2xl font-bold text-white mb-3">Drop files here (Max 10)</h3>
                      <p className="text-slate-500 font-medium tracking-wide">Or click to browse</p>
                    </div>
                  )}
                </div>

                {error && <div className="mt-4 bg-red-500/10 border border-red-500/20 text-red-400 text-sm py-2 px-4 rounded-xl text-center">{error}</div>}

                <div className="mt-6">
                  <button
                    onClick={handleUpload} disabled={files.length === 0 || isLoading}
                    className={`w-full py-5 rounded-2xl font-black text-lg flex items-center justify-center transition-all ${files.length === 0 || isLoading ? 'bg-slate-800 text-slate-600 cursor-not-allowed' : 'btn-primary text-white shadow-orange-500/20 shadow-lg'}`}
                  >
                    {isLoading ? (
                      <div className="flex items-center space-x-3">
                        <svg className="animate-spin h-6 w-6" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                        <span>{loadingMessage || 'Converting Batch...'}</span>
                      </div>
                    ) : `Extract Data from ${files.length} File${files.length === 1 ? '' : 's'}`}
                  </button>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'history' && !previewData && (
            <div className="glass-panel rounded-[2.5rem] p-10">
              <div className="flex justify-between items-end mb-10">
                <div>
                  <h2 className="text-4xl font-black text-white mb-2">My History</h2>
                  <p className="text-slate-500">Access and edit your previous extractions.</p>
                </div>
                <div className="hidden sm:block text-6xl font-black text-white/5 select-none pointer-events-none">OM RECORDS</div>
              </div>

              {isFetchingHistory ? (
                <div className="flex flex-col items-center justify-center py-24 space-y-4">
                  <div className="w-16 h-1 bg-slate-800 rounded-full overflow-hidden relative">
                    <div className="absolute inset-0 bg-orange-500 animate-[loading-bar_1.5s_infinite]"></div>
                  </div>
                  <p className="text-sm font-bold text-slate-500 uppercase tracking-widest">Loading Records...</p>
                </div>
              ) : (
                history.length === 0 ? (
                  <div className="text-center py-24 border-2 border-dashed border-slate-800/50 rounded-3xl">
                    <p className="text-slate-500 text-lg font-medium">No records found yet. Start by converting an image!</p>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {history.map(item => (
                      <div key={item.id} className="glass-panel p-6 rounded-[2rem] hover:border-orange-500/50 transition-all cursor-pointer group" onClick={() => handleViewPreview(item.id)}>
                        <div className="flex justify-between items-start mb-6">
                          <div className="bg-orange-500/10 p-4 rounded-2xl text-orange-500">
                            <svg className="h-8 w-8" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
                          </div>
                          <span className="text-[10px] font-bold text-slate-600 bg-slate-900 border border-slate-800 px-3 py-1 rounded-full">{new Date(item.created_at).toLocaleDateString()}</span>
                        </div>
                        <h3 className="text-xl font-bold text-slate-200 truncate mb-1">{item.original_filename}</h3>
                        <p className="text-xs text-slate-500 mb-6 capitalize">{item.original_filename.split('.').pop()} Extraction</p>
                        <button className="w-full py-3 bg-slate-800 group-hover:bg-orange-500 group-hover:text-white rounded-xl text-slate-400 text-sm font-bold transition-all">View & Edit</button>
                      </div>
                    ))}
                  </div>
                )
              )}
            </div>
          )}

          {previewData && (
            <div className="glass-panel p-10 rounded-[3rem]">
              <div className="flex flex-col md:flex-row justify-between items-center mb-10 gap-6">
                <div className="flex items-center space-x-6">
                  <button onClick={() => { setActiveTab(originalTab); setPreviewData(null); setFiles([]); setPreviews([]); }} className="p-4 bg-slate-900 border border-slate-800 rounded-2xl text-slate-400 hover:text-white transition-all hover:bg-slate-800 shadow-xl">
                    <svg className="h-6 w-6" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M12.707 5.293a1 1 0 110 1.414L9.414 10l3.293 3.293a1 1 0 11-1.414 1.414l-4-4a1 1 0 010-1.414l4-4a1 1 0 111.414 0z" clipRule="evenodd" /></svg>
                  </button>
                  <div>
                    <h2 className="text-3xl font-black text-white mb-1">Batch Result</h2>
                    <p className="text-slate-500 font-medium">Extracted data from up to 10 files combined.</p>
                  </div>
                </div>
                <div className="flex space-x-4">
                  <button onClick={handleSave} disabled={isSaving} className="btn-secondary px-8 py-3 rounded-2xl font-bold text-slate-300">Save Progress</button>
                  <button onClick={handleDownload} className="btn-primary px-10 py-3 rounded-2xl font-black text-white shadow-2xl">Final Download</button>
                </div>
              </div>

              <div className="overflow-auto max-h-[600px] border border-slate-800 rounded-[2rem] custom-scrollbar bg-slate-900/30">
                <table className="w-full text-left border-collapse">
                  <thead className="sticky top-0 bg-slate-900/90 backdrop-blur z-20 shadow-xl">
                    <tr>
                      {previewData.length > 0 && Object.keys(previewData[0]).map(key => (
                        <th key={key} className="p-6 border-r border-slate-800 text-[10px] font-black text-slate-500 uppercase tracking-[0.2em]">{key}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {previewData.map((row, i) => (
                      <tr key={i} className="border-b border-slate-800/50 hover:bg-slate-800/20 transition-colors">
                        {Object.keys(row).map(key => (
                          <td key={key} className="p-0 border-r border-slate-800/50">
                            <input
                              type="text"
                              value={row[key] || ''}
                              onChange={e => handleCellChange(i, key, e.target.value)}
                              className="w-full bg-transparent px-6 py-5 text-sm font-medium text-slate-300 focus:bg-orange-500/5 focus:text-orange-400 outline-none transition-all"
                            />
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

export default App;
